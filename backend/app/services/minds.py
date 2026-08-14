import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MINDS_BUILDER_BASE_URL = "https://build.hellominds.ai/api/v1"
BUILDER_API_KEY_HEADER = "X-Api-Key"
HTTP_TIMEOUT_SECONDS = 30.0

MEMORY_CONTEXT_KEYS = (
    "creator_id",
    "brand_voice",
    "historical_insights",
    "ab_test_history",
    "adaptation_history",
)
MEMORY_CONTEXT_VALUE_LIMIT = 2000


class MindsError(RuntimeError):
    pass


class MindsConfigError(MindsError):
    """Raised when Minds credentials are missing from configuration."""


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


class ExperimentVerdict(BaseModel):
    """Structured verdict returned by the Mind at experiment conclusion."""

    winning_variant_id: str
    reasoning: str

    @field_validator("reasoning")
    @classmethod
    def _require_reasoning(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("reasoning must not be empty")
        return value


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
    manifest is a Minds failure, not a silent fix-up).
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
                raise ValueError(
                    f"{self.platform} {self.surface} requires {feature}"
                )
        if self.surface in ("SHORTS", "LONG_FORM") and len(self.thumbnail_briefs or []) != 3:
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


def _headers() -> dict[str, str]:
    key = get_settings().MINDS_BUILDER_API_KEY
    if not key:
        raise MindsConfigError("MINDS_BUILDER_API_KEY is not configured")
    return {BUILDER_API_KEY_HEADER: key}


def _agent_id() -> str:
    agent_id = get_settings().MINDS_AGENT_ID
    if not agent_id:
        raise MindsConfigError("MINDS_AGENT_ID is not configured")
    return agent_id


def _decode_json(response: httpx.Response, context: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise MindsError(f"{context} returned a non-JSON response") from exc


def _get(path: str) -> httpx.Response:
    try:
        response = httpx.get(
            f"{MINDS_BUILDER_BASE_URL}{path}",
            headers=_headers(),
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise MindsError(f"Builder API request failed: {exc}") from exc
    return response


def _post(path: str, payload: dict[str, Any]) -> httpx.Response:
    try:
        response = httpx.post(
            f"{MINDS_BUILDER_BASE_URL}{path}",
            headers=_headers(),
            json=payload,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise MindsError(f"Builder API request failed: {exc}") from exc
    return response


def fetch_memory(agent_id: str) -> dict[str, Any]:
    """Fetch the Mind's context tree (`GET /minds/{agent_id}/memory`)."""
    response = _get(f"/minds/{agent_id}/memory")
    if response.status_code != 200:
        raise MindsError(f"Memory fetch failed with status {response.status_code}")
    memory = _decode_json(response, "Memory fetch")
    if not isinstance(memory, dict):
        raise MindsError("Memory fetch returned an unexpected shape")
    return memory


def update_memory(agent_id: str, key: str, value: Any) -> bool:
    """Persist an insight key/value on the Mind (`POST /minds/{agent_id}/memory/update`)."""
    response = _post(f"/minds/{agent_id}/memory/update", {"key": key, "value": value})
    if response.status_code != 200:
        raise MindsError(f"Memory update failed with status {response.status_code}")
    payload = _decode_json(response, "Memory update")
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("success"))


def build_memory_context(memory: dict[str, Any]) -> str:
    """Render the memory context tree as a compact prompt fragment."""
    lines: list[str] = []
    for key in MEMORY_CONTEXT_KEYS:
        value = memory.get(key)
        if value is None:
            continue
        rendered = json.dumps(value, ensure_ascii=False)
        if len(rendered) > MEMORY_CONTEXT_VALUE_LIMIT:
            rendered = f"{rendered[:MEMORY_CONTEXT_VALUE_LIMIT]}…"
        lines.append(f"{key}: {rendered}")
    if lines:
        return "\n".join(lines)
    rendered = json.dumps(memory, ensure_ascii=False)
    if len(rendered) > MEMORY_CONTEXT_VALUE_LIMIT:
        rendered = f"{rendered[:MEMORY_CONTEXT_VALUE_LIMIT]}…"
    return rendered


def _build_metadata_prompt(
    transcript: str,
    *,
    duration_seconds: float | None,
    memory_context: str | None,
) -> str:
    memory_block = memory_context if memory_context else "none"
    duration_block = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
    return (
        "You are a short-form content strategist working with a creator. "
        "Score the clip transcript below and produce platform-specific hooks.\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        f"Clip duration: {duration_block}\n\n"
        "Creator memory context (historical insights):\n"
        f"{memory_block}\n\n"
        'Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n'
        '{\n'
        '  "virality_score": 0-100 integer,\n'
        '  "suggested_titles": ["3-5 short titles under 70 characters"],\n'
        '  "platform_hooks": {\n'
        '    "youtube_shorts": ["3-5 hooks"],\n'
        '    "tiktok": ["3-5 hooks"],\n'
        '    "x": ["3-5 hooks"]\n'
        '  }\n'
        '}\n'
        "Rules:\n"
        "- virality_score reflects this clip's engagement potential for this creator.\n"
        "- suggested_titles: hook-driven titles, each under 70 characters.\n"
        "- platform_hooks: tailor each set to the platform's style — YouTube Shorts: "
        "curiosity and retention; TikTok: trend-aware, first-frame hooks; "
        "X: text-first, opinionated or debate-style hooks."
    )


def _parse_json_object(text: str, context: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply, tolerating fences."""
    if text.startswith("```"):
        fenced = text.split("```", 2)
        if len(fenced) >= 2:
            text = fenced[1].removeprefix("json").strip()
    try:
        start, end = text.index("{"), text.rindex("}")
        data = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError) as exc:
        raise MindsError(f"Could not parse {context} JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MindsError(f"{context} returned a non-object body")
    return data


def _parse_metadata(message: str) -> ClipMetadata:
    data = _parse_json_object(message, "clip metadata")
    try:
        return ClipMetadata(**data)
    except ValidationError as exc:
        raise MindsError(f"Clip metadata failed validation: {exc}") from exc


def generate_clip_metadata(
    transcript: str,
    *,
    duration_seconds: float | None = None,
    memory_context: str | None = None,
) -> ClipMetadata:
    """Prompt the Mind to score a clip and return the structured verdict.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable or invalid responses) so callers can degrade gracefully.
    """
    prompt = _build_metadata_prompt(
        transcript, duration_seconds=duration_seconds, memory_context=memory_context
    )
    response = _post(f"/minds/{_agent_id()}/message", {"prompt": prompt})
    if response.status_code != 200:
        raise MindsError(
            f"Clip metadata generation failed with status {response.status_code}"
        )
    message = response.json().get("response")
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Clip metadata response missing 'response' text")
    return _parse_metadata(message)


def _build_winner_prompt(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    memory_context: str | None,
) -> str:
    memory_block = memory_context if memory_context else "none"
    variant_lines = "\n".join(
        f"- variant_id: {variant.get('variant_id')}, "
        f"title: {variant.get('title', '')}, "
        f"thumbnail: {variant.get('thumbnail_path') or 'none'}, "
        f"views: {variant.get('views', 0)}, "
        f"clicks: {variant.get('clicks', 0)}, "
        f"ctr: {variant.get('ctr', 0.0)}%"
        for variant in variants
    )
    return (
        "You are an experiment analyst working with a creator. "
        "An experiment on one of the creator's clips just crossed its view "
        "threshold; study the variants and the clip transcript, then pick the "
        "winning variant and explain why.\n\n"
        f"Platform: {platform}\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        "Experiment variants (thumbnail is the rendered thumbnail file path "
        "viewers saw for that variant):\n"
        f"{variant_lines}\n\n"
        "Creator memory context (brand voice and past learnings):\n"
        f"{memory_block}\n\n"
        'Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n'
        '{\n'
        '  "winning_variant_id": "the id of the winning variant from the list above",\n'
        '  "reasoning": "2-3 sentences: why this variant won and what to reuse next time"\n'
        '}\n'
        "Rules:\n"
        "- winning_variant_id must exactly match one of the variant_id values above.\n"
        "- reasoning must be non-empty and grounded in the variant metrics and clip content.\n"
        "- The reasoning doubles as the learned insight persisted to the creator's memory."
    )


def _parse_winner_verdict(message: str) -> ExperimentVerdict:
    data = _parse_json_object(message, "experiment verdict")
    try:
        return ExperimentVerdict(**data)
    except ValidationError as exc:
        raise MindsError(f"Experiment verdict failed validation: {exc}") from exc


def decide_experiment_winner(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    *,
    memory_context: str | None = None,
) -> ExperimentVerdict:
    """Ask the Mind to pick the winning variant of a concluded experiment.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable verdicts, unknown winner ids, empty reasoning) so callers
    can fail the experiment closed instead of falling back to metrics.
    """
    prompt = _build_winner_prompt(platform, variants, transcript, memory_context)
    response = _post(f"/minds/{_agent_id()}/message", {"prompt": prompt})
    if response.status_code != 200:
        raise MindsError(
            f"Experiment winner decision failed with status {response.status_code}"
        )
    message = response.json().get("response")
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Experiment verdict response missing 'response' text")
    verdict = _parse_winner_verdict(message)
    known_ids = {str(variant.get("variant_id")) for variant in variants if variant.get("variant_id")}
    if not known_ids or verdict.winning_variant_id not in known_ids:
        raise MindsError(
            f"Experiment verdict picked unknown variant id {verdict.winning_variant_id!r}"
        )
    return verdict


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
    ("x", "POST"): (
        "{\n"
        '  "caption": "the post caption",\n'
        '  "hashtags": ["#tag"]\n'
        "}\n"
    ),
}


def _build_adaptation_prompt(
    clip: dict[str, Any],
    platform: str,
    surface: str,
    segments: list[dict[str, Any]],
    memory_context: str | None,
) -> str:
    memory_block = memory_context if memory_context else "none"
    clip_block = (
        f"Clip id: {clip.get('id')}\n"
        f"Clip title: {clip.get('title', '')}\n"
        f"Clip window: [{clip.get('start_time')}s, {clip.get('end_time')}s]\n"
        f"Clip transcript:\n{clip.get('transcript', '')}"
    )
    segment_lines = "\n".join(
        f"- [{segment.get('start')}s → {segment.get('end')}s] {segment.get('text', '')}"
        for segment in segments
    )
    shape = ADAPTATION_FEATURE_SHAPES.get((platform, surface))
    if shape is None:
        raise MindsError(f"Unsupported adaptation target {platform}/{surface}")
    return (
        "You are a platform-native content packager working with a creator. "
        "Author the complete feature manifest for publishing one cut clip on "
        f"the creator's {platform} ({surface}) channel.\n\n"
        f"{clip_block}\n\n"
        "Timed transcript segments:\n"
        f"{segment_lines}\n\n"
        "Creator memory context (brand voice, past insights, previous adaptations):\n"
        f"{memory_block}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n"
        f"{shape}"
        "Rules:\n"
        "- frame_timestamp values must lie inside the clip window "
        f"[{clip.get('start_time')}s, {clip.get('end_time')}s].\n"
        "- youtube surfaces: exactly 3 thumbnail_briefs for Test & Compare.\n"
        "- chapter timestamps are clip-relative seconds inside the clip window.\n"
        "- overlay_spec entries must match spoken segments by content, with a "
        "placement (top|center|bottom) and a style (bold|outlined|italic).\n"
        "- Everything must be grounded in the clip transcript; do not invent facts.\n"
        "- Referencing past adaptations and insights is encouraged; the history "
        "above is the creator's compounding learning."
    )


def _parse_adaptation_features(message: str, platform: str, surface: str) -> AdaptationFeatures:
    data = _parse_json_object(message, "adaptation features")
    if data.get("surface") not in (None, surface):
        raise MindsError(
            f"Adaptation features returned surface {data.get('surface')!r}, "
            f"expected {surface!r}"
        )
    data["platform"] = platform
    data["surface"] = surface
    try:
        return AdaptationFeatures(**data)
    except ValidationError as exc:
        raise MindsError(f"Adaptation features failed validation: {exc}") from exc


def generate_adaptation_features(
    clip: dict[str, Any],
    platform: str,
    surface: str,
    segments: list[dict[str, Any]],
    *,
    memory_context: str | None = None,
) -> AdaptationFeatures:
    """Ask the Mind to author the feature manifest for one platform-surface.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable or invalid manifests) so the adaptation fails closed.
    """
    prompt = _build_adaptation_prompt(clip, platform, surface, segments, memory_context)
    response = _post(f"/minds/{_agent_id()}/message", {"prompt": prompt})
    if response.status_code != 200:
        raise MindsError(
            f"Adaptation features generation failed with status {response.status_code}"
        )
    message = response.json().get("response")
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Adaptation features response missing 'response' text")
    return _parse_adaptation_features(message, platform, surface)
