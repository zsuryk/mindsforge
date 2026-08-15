import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.memory import MemoryEntry

logger = logging.getLogger(__name__)

MINDS_BUILDER_BASE_URL = "https://api.build.hellominds.ai"
BUILDER_API_KEY_HEADER = "X-Api-Key"
HTTP_TIMEOUT_SECONDS = 30.0

# One conversation per Mind carries all of MindsForge's messages. The Mind
# replies asynchronously, so generation calls send a message then poll the
# conversation history until a Mind reply arrives.
MESSAGING_ALIAS = "mindsforge"
MESSAGE_REPLY_TIMEOUT_SECONDS = 180.0
MESSAGE_REPLY_POLL_INTERVAL_SECONDS = 2.0

# Mind replies arrive as senderType 0 (human messages are senderType 1).
MIND_SENDER_TYPE = 0

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


def _get(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    try:
        response = httpx.get(
            f"{MINDS_BUILDER_BASE_URL}{path}",
            headers=_headers(),
            params=params,
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
    """Return the Mind's persistent context tree as a key/value dict.

    The Minds Builder API no longer stores memory, so the tree is persisted
    locally (SQLite) and keyed by agent id.
    """
    with get_session_factory()() as db:
        rows = db.scalars(
            select(MemoryEntry).where(MemoryEntry.agent_id == agent_id)
        ).all()
        return {row.key: row.value for row in rows}


def update_memory(agent_id: str, key: str, value: Any) -> bool:
    """Persist an insight key/value to the local memory tree."""
    with get_session_factory()() as db:
        entry = db.scalar(
            select(MemoryEntry).where(
                MemoryEntry.agent_id == agent_id, MemoryEntry.key == key
            )
        )
        if entry is None:
            db.add(MemoryEntry(agent_id=agent_id, key=key, value=value))
        else:
            entry.value = value
        db.commit()
    return True


def _ensure_conversation(agent_id: str, alias: str = MESSAGING_ALIAS) -> None:
    """Create the message conversation for this Mind if it does not exist."""
    response = _post(
        "/v1/messaging/conversation", {"alias": alias, "mindId": agent_id}
    )
    if response.status_code in (200, 409):
        return
    if _is_alias_already_exists(response):
        return
    raise MindsError(
        f"Failed to create conversation with status {response.status_code}"
    )


def _is_alias_already_exists(response: httpx.Response) -> bool:
    """The Builder API reports a duplicate alias as 400 VALIDATION_FAILED with
    message "alias already exists" rather than a 409, so treat that body as an
    idempotent success."""
    if response.status_code != 400:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    if not isinstance(body, dict):
        return False
    return (body.get("error") or {}).get("message") == "alias already exists"


def _latest_history_fingerprint(alias: str = MESSAGING_ALIAS) -> str | None:
    response = _get(f"/v1/messaging/histories/{alias}", params={"limit": 1})
    if response.status_code != 200:
        raise MindsError(f"History fetch failed with status {response.status_code}")
    rows = _decode_json(response, "History fetch")
    if not isinstance(rows, list) or not rows:
        return None
    fingerprint = rows[0].get("fingerprint")
    return str(fingerprint) if fingerprint else None


def _is_mind_reply(row: dict[str, Any]) -> bool:
    sender_type = row.get("senderType")
    if sender_type is None:
        sender_type = row.get("partyType")
    return sender_type == MIND_SENDER_TYPE


def _fingerprint_recency(fingerprint: str) -> int:
    """Ordering key for a history fingerprint.

    Fingerprints are ``<epoch-ms>_<uuid>``, so the numeric prefix is a
    monotonic recency key: larger means the row is newer.
    """
    prefix = fingerprint.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return 0


def _is_newer_than(row: dict[str, Any], cursor: str | None) -> bool:
    """Whether a history row was created after the cursor fingerprint.

    The Builder history API ignores the ``after`` cursor parameter — it always
    returns the full conversation, newest first — so stale replies to earlier
    prompts must be filtered client-side by fingerprint recency instead.
    """
    if cursor is None:
        return True
    fingerprint = row.get("fingerprint")
    if not fingerprint:
        return False
    return _fingerprint_recency(str(fingerprint)) > _fingerprint_recency(cursor)


def _message_mind(agent_id: str, prompt: str, alias: str = MESSAGING_ALIAS) -> str:
    """Send a prompt to the Mind and block until it replies, returning the text.

    The Builder API messaging flow is asynchronous: create the conversation,
    POST the message, then poll history for a Mind reply (senderType 0) that
    is newer than the message we just sent.
    """
    _ensure_conversation(agent_id, alias)
    cursor = _latest_history_fingerprint(alias)
    response = _post(
        "/v1/messaging/message", {"alias": alias, "messageText": prompt}
    )
    if response.status_code != 200:
        raise MindsError(f"Message send failed with status {response.status_code}")

    deadline = time.monotonic() + MESSAGE_REPLY_TIMEOUT_SECONDS
    while True:
        history = _get(
            f"/v1/messaging/histories/{alias}",
            params={"limit": 50},
        )
        if history.status_code != 200:
            raise MindsError(f"History fetch failed with status {history.status_code}")
        rows = _decode_json(history, "History fetch")
        if not isinstance(rows, list):
            raise MindsError("History fetch returned an unexpected shape")
        for row in rows:
            if not _is_newer_than(row, cursor):
                continue
            if _is_mind_reply(row):
                text = row.get("messageText")
                if isinstance(text, str) and text.strip():
                    return text
        if time.monotonic() > deadline:
            raise MindsError("Timed out waiting for a Mind reply")
        time.sleep(MESSAGE_REPLY_POLL_INTERVAL_SECONDS)


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


def _build_metadata_read_prompt(
    transcript: str,
    *,
    duration_seconds: float | None,
    memory_context: str | None,
) -> str:
    duration_block = (
        f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
    )
    memory_block = (
        "Creator memory context (brand voice, past insights):\n"
        f"{memory_context}\n\n"
        if memory_context
        else "There is no creator memory or brand voice attached to this clip, "
        "so judge purely the content.\n\n"
    )
    return (
        "I need your honest read on a clip. You are not fabricating anything: "
        "estimate engagement potential as best you can from the transcript alone. "
        "A low score (even 0) is a completely valid answer, and doubt is allowed.\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        f"Clip duration: {duration_block}\n\n"
        f"{memory_block}"
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
        raise MindsError(
            f"{context} reply contained no JSON object — the Mind may have "
            f"refused the prompt or replied in prose; reply was: {preview!r}"
        )
    try:
        start, end = text.index("{"), text.rindex("}")
        data = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError) as exc:
        raise MindsError(
            f"Could not parse {context} JSON: {exc}; reply was: {preview!r}"
        ) from exc
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
    conversation_alias: str | None = None,
) -> ClipMetadata:
    """Prompt the Mind to score a clip and return the structured verdict.

    The Mind answers in two steps: first an honest prose read — which it gives
    readily even for brandless or meme content when framed as estimation rather
    than fabrication — then a schema-fill message converting that read into the
    structured verdict. A single-message JSON-only prompt reads as "fabricate a
    score" to the Mind and triggers refusals that fail the job. If the read
    already contains a parseable verdict, the fill step is skipped.

    ``conversation_alias`` isolates this prompt in its own conversation when
    provided. Retrying a job re-sends byte-identical prompts for the same
    clips; without isolation the Mind sees the same templated prompt repeated
    in one conversation and eventually refuses to answer, which then fails the
    job (ADR-0002). Fresh conversations per attempt prevent that build-up.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable or invalid responses) so callers can degrade gracefully.
    """
    alias = conversation_alias or MESSAGING_ALIAS
    agent_id = _agent_id()
    read_prompt = _build_metadata_read_prompt(
        transcript, duration_seconds=duration_seconds, memory_context=memory_context
    )
    read = _message_mind(agent_id, read_prompt, alias=alias)
    if not isinstance(read, str) or not read.strip():
        raise MindsError("Clip metadata response missing 'response' text")
    try:
        return _parse_metadata(read)
    except MindsError:
        fill = _build_metadata_fill_prompt()
        message = _message_mind(agent_id, fill, alias=alias)
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
        "Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n"
        "{\n"
        '  "winning_variant_id": "the id of the winning variant from the list above",\n'
        '  "reasoning": "2-3 sentences: why this variant won and what to reuse next time"\n'
        "}\n"
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
    message = _message_mind(_agent_id(), prompt)
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Experiment verdict response missing 'response' text")
    verdict = _parse_winner_verdict(message)
    known_ids = {
        str(variant.get("variant_id"))
        for variant in variants
        if variant.get("variant_id")
    }
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
    ("x", "POST"): ('{\n  "caption": "the post caption",\n  "hashtags": ["#tag"]\n}\n'),
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


def _parse_adaptation_features(
    message: str, platform: str, surface: str
) -> AdaptationFeatures:
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
    message = _message_mind(_agent_id(), prompt)
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Adaptation features response missing 'response' text")
    return _parse_adaptation_features(message, platform, surface)
