import json
import logging
from collections.abc import Callable
from typing import Any, Literal, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.chat import ChatMessageRow
from app.models.memory import MemoryEntry

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


HEALTH_TIMEOUT_SECONDS = 5.0


def check_connection() -> str:
    """Reachability probe of the configured LLM backend for the health endpoint.

    Returns "unconfigured" when the endpoint is missing configuration, "ok"
    when ``GET {OPENAI_BASE_URL}/models`` answers, and "down" otherwise
    (request errors, timeouts, non-200 responses). The probe is deliberately
    short so the health endpoint stays snappy.
    """
    settings = get_settings()
    if not is_configured():
        return "unconfigured"
    try:
        response = httpx.get(
            f"{settings.OPENAI_BASE_URL.rstrip('/')}/models",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT_SECONDS,
        )
    except httpx.RequestError:
        return "down"
    return "ok" if response.status_code == 200 else "down"


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



SYSTEM_MARKER = "[MindsForge] "

CHAT_THREAD_ID = "default"

LOCAL_AGENT_ID = "default"

CHAT_INIT_INSTRUCTION = (
    f"{SYSTEM_MARKER}You are this creator's content strategist. Ground every "
    "answer in this conversation and in the creator's memory. When the creator "
    "states a brand rule — a preference about how their content should look, "
    "sound, or be packaged — acknowledge it and remember it. When you score "
    "clips or generate adaptations, explicitly reference what you remember "
    "about this creator's preferences and past results. Reference specific "
    "rules and experiments when they are relevant. You may use your "
    "own Tavily connection to research trends when asked open-ended questions."
)


class ChatMessage(BaseModel):
    """A single row of the creator chat thread.

    Role mapping: senderType 0 rows are the Mind; senderType 1 rows prefixed
    with the system marker are the app's own notifications (marker stripped);
    any other senderType 1 row is the creator's message.
    """

    role: Literal["user", "mind", "system"]
    text: str
    fingerprint: str | None = None


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


def _insert_chat_row(role: str, text: str) -> None:
    with get_session_factory()() as session:
        session.add(
            ChatMessageRow(role=role, text=text, thread_id=CHAT_THREAD_ID)
        )
        session.commit()


def _chat_rows(limit: int | None = None) -> list[ChatMessageRow]:
    with get_session_factory()() as session:
        stmt = (
            select(ChatMessageRow)
            .where(ChatMessageRow.thread_id == CHAT_THREAD_ID)
            .order_by(ChatMessageRow.created_at.asc(), ChatMessageRow.id.asc())
        )
        rows = list(session.scalars(stmt).all())
    return rows[-limit:] if limit is not None else rows


def _ensure_chat_initialised() -> None:
    """Insert the system-marked initialisation instruction when the local
    chat thread is empty, so the Mind is primed before the creator's first
    message — or before any background notification that lands first."""
    if not _chat_rows(limit=1):
        _insert_chat_row("system", CHAT_INIT_INSTRUCTION)


def _chat_messages() -> list[dict[str, str]]:
    """Render the stored thread as chat completion messages."""
    roles = {"system": "system", "user": "user", "mind": "assistant"}
    messages: list[dict[str, str]] = []
    for row in _chat_rows():
        text = row.text
        if text.startswith(SYSTEM_MARKER):
            text = text[len(SYSTEM_MARKER) :]
        messages.append({"role": roles[row.role], "content": text})
    return messages


def send_chat_message(text: str) -> str:
    """Send a creator message to the Mind and return its reply.

    The local SQLite thread is the conversation: it is initialised with the
    system instruction when empty, the creator message is stored, and the
    whole thread (creator turns, Mind turns, and notifications) is replayed
    as the prompt. The reply is stored as the next Mind turn.

    Raises LLMError on any failure — fail-closed, no fallback text.
    """
    _headers()
    _ensure_chat_initialised()
    _insert_chat_row("user", text)
    reply = _chat_completion(_chat_messages())
    _insert_chat_row("mind", reply)
    return reply


def post_chat_notification(text: str) -> None:
    """Store a system-marked notification in the local chat thread.

    The message is prefixed with the system marker so the UI renders it as a
    chip and the Mind reads it as an event in the thread (e.g. trend research
    results it can answer grounded in). The thread is initialised first when
    it is empty, mirroring ``send_chat_message``.
    """
    _ensure_chat_initialised()
    _insert_chat_row("system", f"{SYSTEM_MARKER}{text}")


def notify_mind(text: str) -> None:
    """Tell the Mind about an outcome it did not witness, best-effort.

    Stores ``text`` as a system-marked message in the local chat thread so
    the outcome is recorded where the Mind's context is built from. Any
    error — including an unconfigured builder — is logged and swallowed: a
    notification must never fail an Experiment or Adaptation that already
    succeeded (fire-and-forget by design, no reply waiting).
    """
    try:
        post_chat_notification(text)
    except Exception as exc:
        logger.warning("Mind notification not delivered: %s", exc)


def fetch_chat_history(limit: int = 50) -> list[ChatMessage]:
    """Return the chat thread as role-annotated messages, oldest first."""
    messages: list[ChatMessage] = []
    for row in _chat_rows(limit=limit):
        text = row.text
        if not isinstance(text, str) or not text.strip():
            continue
        if row.role == "system":
            role: Literal["user", "mind", "system"] = "system"
            if text.startswith(SYSTEM_MARKER):
                text = text[len(SYSTEM_MARKER) :]
        elif row.role == "mind":
            role = "mind"
        else:
            role = "user"
        messages.append(
            ChatMessage(role=role, text=text, fingerprint=row.id)
        )
    return messages


CHAT_CONTEXT_MAX_CHARS = 4000


def build_chat_context() -> str | None:
    """Render the local chat thread as a prompt fragment.

    Filters to meaningful messages (creator, Mind, and system
    notifications), renders them with role annotations, and caps the output
    at ``CHAT_CONTEXT_MAX_CHARS`` characters so the prompt stays within
    token budgets.

    The system initialisation instruction is excluded — it is setup, not
    memory. Returns ``None`` when the thread is empty (best-effort, callers
    degrade gracefully).
    """
    rows = _chat_rows()
    lines: list[str] = []
    char_count = 0
    for row in reversed(rows):
        text = row.text
        if not isinstance(text, str) or not text.strip():
            continue
        if text == CHAT_INIT_INSTRUCTION:
            continue
        if row.role == "mind":
            role_label = "Mind"
            text_rendered = text
        elif row.role == "system":
            role_label = "[System]"
            text_rendered = (
                text[len(SYSTEM_MARKER) :]
                if text.startswith(SYSTEM_MARKER)
                else text
            )
        else:
            role_label = "Creator"
            text_rendered = text
        line = f"{role_label}: {text_rendered}"
        if char_count + len(line) + 1 > CHAT_CONTEXT_MAX_CHARS:
            break
        lines.append(line)
        char_count += len(line) + 1
    if not lines:
        return None
    lines.reverse()
    return "\n".join(lines)


def _build_winner_read_prompt(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    chat_context: str | None,
) -> str:
    context_block = chat_context if chat_context else "none"
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
        "I need your honest read on an A/B experiment. You are not fabricating "
        "anything: study the variants and the clip transcript, then tell me "
        "which variant won and why. A clear reasoning grounded in the data is "
        "what matters.\n\n"
        f"Platform: {platform}\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        "Experiment variants (thumbnail is the rendered thumbnail file path "
        "viewers saw for that variant):\n"
        f"{variant_lines}\n\n"
        "Creator conversation context (brand voice and past learnings):\n"
        f"{context_block}\n\n"
        "Give me your read in prose: which variant should win, why it "
        "outperformed the others, and what the creator should reuse next time. "
        "I will then ask you to convert it into a structured verdict."
    )


_EXPERIMENT_VERDICT_SCHEMA = (
    "{\n"
    '  "winning_variant_id": "the id of the winning variant from the list above",\n'
    '  "reasoning": "2-3 sentences: why this variant won and what to reuse next time"\n'
    "}"
)


def _build_winner_fill_prompt() -> str:
    return (
        "Here is the schema for the experiment verdict. Fill it in with your "
        "read from your last message:\n"
        f"{_EXPERIMENT_VERDICT_SCHEMA}\n\n"
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
        raise LLMError(f"Experiment verdict failed validation: {exc}") from exc


def decide_experiment_winner(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    *,
    chat_context: str | None = None,
) -> ExperimentVerdict:
    """Ask the Mind to pick the winning variant of a concluded experiment.

    Two-step flow mirrors clip scoring (see ``generate_clip_metadata``): a
    prose read of the variants, then a schema-fill message converting that
    read into the structured verdict.

    Raises LLMError on any failure (missing configuration, HTTP errors,
    unparseable verdicts, unknown winner ids, empty reasoning) so callers
    fail the experiment closed instead of falling back to metrics.
    """
    read_prompt = _build_winner_read_prompt(platform, variants, transcript, chat_context)

    def parse(message: str) -> ExperimentVerdict:
        verdict = _parse_winner_verdict(message)
        known_ids = {
            str(variant.get("variant_id"))
            for variant in variants
            if variant.get("variant_id")
        }
        if not known_ids or verdict.winning_variant_id not in known_ids:
            raise LLMError(
                f"Experiment verdict picked unknown variant id "
                f"{verdict.winning_variant_id!r}"
            )
        return verdict

    return _read_then_fill(read_prompt, _build_winner_fill_prompt, parse)


def fetch_memory() -> dict[str, Any]:
    """Return the Mind's persistent context tree as a key/value dict.

    The tree is persisted locally (SQLite) under the local agent id.
    """
    with get_session_factory()() as db:
        rows = db.scalars(
            select(MemoryEntry).where(MemoryEntry.agent_id == LOCAL_AGENT_ID)
        ).all()
        return {row.key: row.value for row in rows}


def update_memory(key: str, value: Any) -> bool:
    """Persist an insight key/value to the local memory tree."""
    with get_session_factory()() as db:
        entry = db.scalar(
            select(MemoryEntry).where(
                MemoryEntry.agent_id == LOCAL_AGENT_ID, MemoryEntry.key == key
            )
        )
        if entry is None:
            db.add(MemoryEntry(agent_id=LOCAL_AGENT_ID, key=key, value=value))
        else:
            entry.value = value
        db.commit()
    return True
