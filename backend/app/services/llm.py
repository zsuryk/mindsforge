import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Any failure of an LLM call: configuration, transport, or response shape."""


class LLMConfigError(LLMError):
    """Raised when the LLM backend is missing required configuration."""


def _requires_api_key() -> bool:
    """Whether the configured endpoint authenticates requests.

    OpenAI's own endpoints require a key; local servers (Ollama, LM Studio,
    vLLM) ignore auth, so an empty OPENAI_API_KEY is valid there.
    """
    host = urlparse(get_settings().OPENAI_BASE_URL).hostname or ""
    return host == "openai.com" or host.endswith(".openai.com")


def is_configured() -> bool:
    """Whether the LLM backend has everything it needs to be called."""
    settings = get_settings()
    if not settings.OPENAI_BASE_URL:
        return False
    return not (_requires_api_key() and not settings.OPENAI_API_KEY)


def _headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.OPENAI_BASE_URL:
        raise LLMConfigError("OPENAI_BASE_URL is not configured")
    if _requires_api_key() and not settings.OPENAI_API_KEY:
        raise LLMConfigError("OPENAI_API_KEY is not configured")
    headers = {"Content-Type": "application/json"}
    if settings.OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
    return headers


def check_connection() -> str:
    """Configuration probe for the health endpoint.

    Returns "unconfigured" when the endpoint is missing configuration. The
    live reachability probe lands with the Minds Builder removal.
    """
    return "ok" if is_configured() else "unconfigured"


def _chat_completion(
    messages: list[dict[str, str]], *, timeout_seconds: float | None = None
) -> str:
    """One chat completion against the configured OpenAI-compatible endpoint.

    Fail-closed (ADR-0002): transport errors, non-200 responses, and
    unusable response shapes all raise LLMError rather than degrading.
    """
    settings = get_settings()
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.OPENAI_TIMEOUT_SECONDS
    )
    try:
        response = httpx.post(
            f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers=_headers(),
            json={"model": settings.OPENAI_MODEL, "messages": messages},
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    if response.status_code != 200:
        preview = response.text[:200] if response.text else ""
        raise LLMError(
            f"LLM request failed with status {response.status_code}: {preview}"
        )
    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"LLM returned an unexpected response shape: {exc}") from exc
    if not isinstance(text, str) or not text.strip():
        raise LLMError("LLM returned an empty reply")
    return text


_T = TypeVar("_T")


def _read_then_fill(
    read_prompt: str, fill_prompt: Callable[[], str], parse: Callable[[str], _T]
) -> _T:
    """Ask for a prose read, then convert that read into the schema.

    A single JSON-only prompt reads as "fabricate an answer" and reliably
    draws prose refusals; the read-then-fill flow keeps the model honest.
    If the read already parses, the fill step is skipped.
    """
    read = _chat_completion([{"role": "user", "content": read_prompt}])
    try:
        return parse(read)
    except LLMError:
        fill = _chat_completion(
            [
                {"role": "user", "content": read_prompt},
                {"role": "assistant", "content": read},
                {"role": "user", "content": fill_prompt()},
            ]
        )
        return parse(fill)


class ClipMetadata(BaseModel):
    """Structured verdict returned by the Mind for a single clip."""

    virality_score: int
    suggested_titles: list[str]
    platform_hooks: dict[str, list[str]]

    @field_validator("virality_score")
    @classmethod
    def _clamp_score(cls, value: int) -> int:
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError("virality_score must be an integer") from exc



class ThumbnailBrief(BaseModel):
    """A Test & Compare-style thumbnail concept authored by the Mind."""

    frame_timestamp: float
    overlay_text: str


class ChapterItem(BaseModel):
    title: str
    timestamp: float


class CommunityPoll(BaseModel):
    question: str
    options: list[str]


class QuizItem(BaseModel):
    question: str
    answer: str


class OverlaySpecItem(BaseModel):
    text: str
    placement: str
    style: str


class StickerSuggestion(BaseModel):
    emoji: str
    placement: str


class AdaptationFeatures(BaseModel):
    """Feature manifest authored by the Mind for one platform-surface pair.

    Surfaces exercise different subsets of the fields; `_check_surface_shape`
    enforces the manifest shape for the targeted pair (ADR-0002: an invalid
    manifest is a hard failure, not a silent fix-up).
    """

    platform: str
    surface: str
    chapters: list[ChapterItem] | None = None
    tags: list[str] | None = None
    poll: CommunityPoll | None = None
    quiz: list[QuizItem] | None = None
    thumbnail_briefs: list[ThumbnailBrief] | None = None
    shorts_link: str | None = None
    platform_hooks: list[str] | None = None
    overlay_spec: list[OverlaySpecItem] | None = None
    caption_style: str | None = None
    stickers: list[StickerSuggestion] | None = None
    pinned_comment: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None

    @model_validator(mode="after")
    def _check_surface_shape(self) -> "AdaptationFeatures":
        required = _ADAPTATION_REQUIRED_FEATURES.get((self.platform, self.surface))
        if required is None:
            raise ValueError(
                f"Unsupported adaptation target {self.platform}/{self.surface}"
            )
        for feature in required:
            if not _present(getattr(self, feature)):
                raise ValueError(f"{self.platform} {self.surface} requires {feature}")
        if (
            self.surface in ("SHORTS", "LONG_FORM")
            and len(self.thumbnail_briefs or []) != 3
        ):
            raise ValueError(
                f"{self.platform} {self.surface} requires exactly 3 thumbnail_briefs"
            )
        return self



def _present(value: object) -> bool:
    """A required feature is present and non-empty (lists must not be empty)."""
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True



_ADAPTATION_REQUIRED_FEATURES: dict[tuple[str, str], tuple[str, ...]] = {
    ("youtube", "SHORTS"): ("thumbnail_briefs", "platform_hooks"),
    ("youtube", "LONG_FORM"): (
        "chapters",
        "tags",
        "poll",
        "quiz",
        "thumbnail_briefs",
        "shorts_link",
    ),
    ("tiktok", "POST"): (
        "overlay_spec",
        "caption_style",
        "stickers",
        "pinned_comment",
    ),
    ("x", "POST"): ("caption", "hashtags"),
}



def _build_metadata_read_prompt(
    transcript: str,
    *,
    duration_seconds: float | None,
    chat_context: str | None,
) -> str:
    duration_block = (
        f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
    )
    context_block = (
        "Creator conversation context (brand voice, past insights, preferences):\n"
        f"{chat_context}\n\n"
        if chat_context
        else "There is no creator conversation context attached to this clip, "
        "so judge purely the content.\n\n"
    )
    return (
        "I need your honest read on a clip. You are not fabricating anything: "
        "estimate engagement potential as best you can from the transcript alone. "
        "A low score (even 0) is a completely valid answer, and doubt is allowed.\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        f"Clip duration: {duration_block}\n\n"
        f"{context_block}"
        "Give me your read in prose: what this clip is, who it is for, and its "
        "rough engagement potential. I will then ask you to convert it into a "
        "structured verdict."
    )


_METADATA_VERDICT_SCHEMA = (
    "{\n"
    '  "virality_score": 0-100 integer (your honest estimate; a low number is valid),\n'
    '  "suggested_titles": ["3-5 short titles under 70 characters"],\n'
    '  "platform_hooks": {\n'
    '    "youtube_shorts": ["3-5 hooks"],\n'
    '    "tiktok": ["3-5 hooks"],\n'
    '    "x": ["3-5 hooks"]\n'
    "  }\n"
    "}"
)


def _build_metadata_fill_prompt() -> str:
    return (
        "Here is the schema for the structured verdict. Fill it in with your "
        "read from your last message:\n"
        f"{_METADATA_VERDICT_SCHEMA}"
    )


def _parse_json_object(text: str, context: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply, tolerating fences."""
    if text.startswith("```"):
        fenced = text.split("```", 2)
        if len(fenced) >= 2:
            text = fenced[1].removeprefix("json").strip()
    preview = f"{text[:200]}…" if len(text) > 200 else text
    if "{" not in text:
        raise LLMError(
            f"{context} reply contained no JSON object — the Mind may have "
            f"refused the prompt or replied in prose; reply was: {preview!r}"
        )
    try:
        start, end = text.index("{"), text.rindex("}")
        data = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError) as exc:
        # A reply that is prose but happens to contain braces (e.g. the Mind
        # quoting the prompt shape while refusing) must not leak a cryptic
        # json.JSONDecodeError; name the likely refusal instead. A reply that
        # is essentially all JSON with a syntax error keeps the parse detail.
        if text[:start].strip() or text[end + 1 :].strip():
            raise LLMError(
                f"{context} reply contained no JSON object — the Mind may have "
                f"refused the prompt or replied in prose; reply was: {preview!r}"
            ) from exc
        raise LLMError(
            f"Could not parse {context} JSON: {exc}; reply was: {preview!r}"
        ) from exc
    if not isinstance(data, dict):
        raise LLMError(f"{context} returned a non-object body")
    return data


def _parse_metadata(message: str) -> ClipMetadata:
    data = _parse_json_object(message, "clip metadata")
    try:
        return ClipMetadata(**data)
    except ValidationError as exc:
        raise LLMError(f"Clip metadata failed validation: {exc}") from exc


ADAPTATION_FEATURE_SHAPES: dict[tuple[str, str], str] = {
    ("youtube", "LONG_FORM"): (
        "{\n"
        '  "chapters": [{"title": "Hook", "timestamp": 2.5}],\n'
        '  "tags": ["tag one", "tag two"],\n'
        '  "poll": {"question": "Which take is right?", "options": ["A", "B"]},\n'
        '  "quiz": [{"question": "Q?", "answer": "A"}],\n'
        '  "thumbnail_briefs": [{"frame_timestamp": 12.0, "overlay_text": "Bold hook"}],\n'
        '  "shorts_link": "title of a related Short of this creator"\n'
        "}\n"
    ),
    ("youtube", "SHORTS"): (
        "{\n"
        '  "thumbnail_briefs": [{"frame_timestamp": 12.0, "overlay_text": "Bold hook"}],\n'
        '  "platform_hooks": ["first-frame hook text"]\n'
        "}\n"
    ),
    ("tiktok", "POST"): (
        "{\n"
        '  "overlay_spec": [{"text": "caption text", "placement": "center", "style": "bold"}],\n'
        '  "caption_style": "auto-caption styling note",\n'
        '  "stickers": [{"emoji": "🔥", "placement": "top-right"}],\n'
        '  "pinned_comment": "pinned comment text"\n'
        "}\n"
    ),
    ("x", "POST"): ('{\n  "caption": "the post caption",\n  "hashtags": ["#tag"]\n}\n'),
}


_ADAPTATION_RULES = (
    "Rules:\n"
    "- frame_timestamp values must lie inside the clip window "
    "[{start}s, {end}s].\n"
    "- youtube surfaces: exactly 3 thumbnail_briefs for Test & Compare.\n"
    "- chapter timestamps are clip-relative seconds inside the clip window.\n"
    "- overlay_spec entries must match spoken segments by content, with a "
    "placement (top|center|bottom) and a style (bold|outlined|italic).\n"
    "- Everything must be grounded in the clip transcript; do not invent facts.\n"
    "- Referencing past adaptations and insights is encouraged; the history "
    "above is the creator's compounding learning."
)


def _adaptation_clip_block(clip: dict[str, Any]) -> str:
    return (
        f"Clip id: {clip.get('id')}\n"
        f"Clip title: {clip.get('title', '')}\n"
        f"Clip window: [{clip.get('start_time')}s, {clip.get('end_time')}s]\n"
        f"Clip transcript:\n{clip.get('transcript', '')}"
    )


def _adaptation_segment_block(segments: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- [{segment.get('start')}s → {segment.get('end')}s] {segment.get('text', '')}"
        for segment in segments
    )


def _adaptation_shape(platform: str, surface: str) -> str:
    shape = ADAPTATION_FEATURE_SHAPES.get((platform, surface))
    if shape is None:
        raise LLMError(f"Unsupported adaptation target {platform}/{surface}")
    return shape


def _build_adaptation_read_prompt(
    clip: dict[str, Any],
    platform: str,
    surface: str,
    segments: list[dict[str, Any]],
    chat_context: str | None,
) -> str:
    """Prose honest read of how to package the clip — no JSON demanded, so the
    Mind can engage honestly without reading the prompt as a fabrication ask.
    A schema-fill message (see ``_build_adaptation_fill_prompt``) converts the
    read into the structured manifest afterwards (ADR-0002, two-step flow)."""
    context_block = chat_context if chat_context else "none"
    return (
        "I need your honest read on a clip before packaging it. You are not "
        "fabricating anything: everything must be grounded in the clip "
        "transcript; do not invent facts.\n\n"
        f"{_adaptation_clip_block(clip)}\n\n"
        "Timed transcript segments:\n"
        f"{_adaptation_segment_block(segments)}\n\n"
        "Creator conversation context (brand voice, past insights, previous adaptations):\n"
        f"{context_block}\n\n"
        "Give me your read in prose: what this clip is, who it is for, and how "
        f"you would package it for the creator's {platform} ({surface}) channel "
        "— which features fit, what the caption/hooks/overlays should say, and "
        "which frames to pull for thumbnails. I will then ask you to convert it "
        "into the structured feature manifest."
    )


def _build_adaptation_fill_prompt(
    clip: dict[str, Any],
    platform: str,
    surface: str,
) -> str:
    """Schema-fill message converting the prose read into the feature manifest."""
    shape = _adaptation_shape(platform, surface)
    return (
        "Here is the schema for the feature manifest. Fill it in with your read "
        "from your last message:\n"
        f"{shape}"
        f"{_ADAPTATION_RULES.format(start=clip.get('start_time'), end=clip.get('end_time'))}"
    )


def _parse_adaptation_features(
    message: str, platform: str, surface: str
) -> AdaptationFeatures:
    data = _parse_json_object(message, "adaptation features")
    if data.get("surface") not in (None, surface):
        raise LLMError(
            f"Adaptation features returned surface {data.get('surface')!r}, "
            f"expected {surface!r}"
        )
    data["platform"] = platform
    data["surface"] = surface
    try:
        return AdaptationFeatures(**data)
    except ValidationError as exc:
        raise LLMError(f"Adaptation features failed validation: {exc}") from exc


def generate_clip_metadata(
    transcript: str,
    *,
    duration_seconds: float | None = None,
    chat_context: str | None = None,
) -> ClipMetadata:
    """Prompt the LLM to score a clip and return the structured verdict.

    Two-step flow: an honest prose read first (which the model gives readily
    even for brandless content when framed as estimation rather than
    fabrication), then a schema-fill message converting that read into the
    structured verdict.

    Raises LLMError on any failure (missing configuration, HTTP errors,
    unparseable or invalid responses) so callers can fail closed.
    """
    read_prompt = _build_metadata_read_prompt(
        transcript, duration_seconds=duration_seconds, chat_context=chat_context
    )
    return _read_then_fill(
        read_prompt, _build_metadata_fill_prompt, _parse_metadata
    )


def generate_adaptation_features(
    clip: dict[str, Any],
    platform: str,
    surface: str,
    segments: list[dict[str, Any]],
    *,
    chat_context: str | None = None,
) -> AdaptationFeatures:
    """Ask the LLM to author the feature manifest for one platform-surface.

    Two-step flow mirrors clip scoring (see ``generate_clip_metadata``): a
    prose read of how to package the clip, then a schema-fill message that
    converts that read into the manifest.

    Raises LLMError on any failure (missing configuration, HTTP errors,
    unparseable or invalid manifests) so the adaptation fails closed.
    """
    read_prompt = _build_adaptation_read_prompt(
        clip, platform, surface, segments, chat_context
    )

    def parse(message: str) -> AdaptationFeatures:
        return _parse_adaptation_features(message, platform, surface)

    return _read_then_fill(
        read_prompt,
        lambda: _build_adaptation_fill_prompt(clip, platform, surface),
        parse,
    )
