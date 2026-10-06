import logging
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.chat import ChatMessageRow
from app.models.memory import MemoryEntry
from app.services.llm import LLMConfigError, LLMError, _parse_json_object

logger = logging.getLogger(__name__)

MINDS_BUILDER_BASE_URL = "https://api.build.hellominds.ai"
BUILDER_API_KEY_HEADER = "X-Api-Key"
HTTP_TIMEOUT_SECONDS = 30.0
MINDS_HEALTH_TIMEOUT_SECONDS = 5.0

# One conversation per Mind carries all of MindsForge's messages. The Mind
# replies asynchronously, so generation calls send a message then poll the
# conversation history until a Mind reply arrives.
MESSAGING_ALIAS = "mindsforge"
# The Mind's reply latency is long-tailed (median ~90s, observed up to 380s+,
# trending up as it engages with repeated prompts). The deadline must sit
# above that tail; 180s was too tight and failed adaptations even though the
# Mind eventually answered. Two-step flows (read + fill) need two round trips,
# so a single prompt's budget is deliberately generous.
MESSAGE_REPLY_TIMEOUT_SECONDS = 600.0
MESSAGE_REPLY_POLL_INTERVAL_SECONDS = 2.0

# Chat lives on its own conversation. Replies are short and were measured at
# ~15s, so the deadline is fast: a hung reply fails the request instead of
# stalling the demo.
CHAT_ALIAS = "mindsforge-chat"
CHAT_REPLY_TIMEOUT_SECONDS = 180.0

# The app's own messages in the chat thread (notifications, trend results,
# initialisation) are senderType-1 rows prefixed with this marker. The Mind
# reads them as normal content; the UI renders them as system chips and strips
# the prefix.
SYSTEM_MARKER = "[MindsForge] "

CHAT_THREAD_ID = "default"

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

# Mind replies arrive as senderType 0 (human messages are senderType 1).
MIND_SENDER_TYPE = 0


# Transitional aliases: the domain error now lives in the LLM client and is
# shared by both services until the Minds Builder path is removed.
MindsError = LLMError
MindsConfigError = LLMConfigError


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


def check_connection() -> str:
    """Lightweight reachability probe of the Minds Builder API.

    Returns "unconfigured" when credentials are missing, "ok" when the API
    answers an authenticated history fetch, and "down" otherwise (request
    errors, timeouts, or non-200 responses). Uses a short timeout so the
    health endpoint stays snappy.
    """
    if not get_settings().MINDS_BUILDER_API_KEY or not get_settings().MINDS_AGENT_ID:
        return "unconfigured"
    try:
        response = httpx.get(
            f"{MINDS_BUILDER_BASE_URL}/v1/messaging/histories/{MESSAGING_ALIAS}",
            headers=_headers(),
            params={"limit": 1},
            timeout=MINDS_HEALTH_TIMEOUT_SECONDS,
        )
    except httpx.RequestError:
        return "down"
    return "ok" if response.status_code == 200 else "down"


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


def _history_rows(alias: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch the conversation history for an alias, newest row first."""
    response = _get(f"/v1/messaging/histories/{alias}", params={"limit": limit})
    if response.status_code != 200:
        raise MindsError(f"History fetch failed with status {response.status_code}")
    rows = _decode_json(response, "History fetch")
    if not isinstance(rows, list):
        raise MindsError("History fetch returned an unexpected shape")
    return rows


def _latest_history_fingerprint(alias: str = MESSAGING_ALIAS) -> str | None:
    rows = _history_rows(alias, limit=1)
    if not rows:
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


def _message_mind(
    agent_id: str,
    prompt: str,
    alias: str = MESSAGING_ALIAS,
    timeout_seconds: float | None = None,
) -> str:
    """Send a prompt to the Mind and block until it replies, returning the text.

    The Builder API messaging flow is asynchronous: create the conversation,
    POST the message, then poll history for a Mind reply (senderType 0) that
    is newer than the message we just sent.

    ``timeout_seconds`` bounds how long to wait for the reply: scoring flows
    keep the generous default while chat passes a fast chat timeout.
    """
    _ensure_conversation(agent_id, alias)
    cursor = _latest_history_fingerprint(alias)
    response = _post(
        "/v1/messaging/message", {"alias": alias, "messageText": prompt}
    )
    if response.status_code != 200:
        raise MindsError(f"Message send failed with status {response.status_code}")

    deadline = time.monotonic() + (
        timeout_seconds if timeout_seconds is not None else MESSAGE_REPLY_TIMEOUT_SECONDS
    )
    while True:
        for row in _history_rows(alias, limit=50):
            if not _is_newer_than(row, cursor):
                continue
            if _is_mind_reply(row):
                text = row.get("messageText")
                if isinstance(text, str) and text.strip():
                    return text
        if time.monotonic() > deadline:
            raise MindsError("Timed out waiting for a Mind reply")
        time.sleep(MESSAGE_REPLY_POLL_INTERVAL_SECONDS)


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


def send_chat_message(text: str) -> str:
    """Send a creator message to the Mind on the dedicated chat conversation.

    Uses the ``mindsforge-chat`` alias so chat traffic never mixes with the
    structured scoring/adaptation conversations. When the thread is empty, a
    system-marked initialisation instruction is stored first so the Mind is
    primed before the creator's first message.

    The local SQLite thread is the record: the creator message is persisted,
    the Mind's reply is fetched from the existing remote call (for now), and
    the reply is persisted as well.

    Raises MindsError on any failure (missing credentials, HTTP errors, or a
    reply that exceeds the chat timeout) — fail-closed, no fallback text.
    """
    _agent_id()
    _ensure_chat_initialised()
    _insert_chat_row("user", text)
    reply = _message_mind(
        _agent_id(), text, alias=CHAT_ALIAS, timeout_seconds=CHAT_REPLY_TIMEOUT_SECONDS
    )
    _insert_chat_row("mind", reply)
    return reply


def post_chat_notification(text: str) -> None:
    """Store a system-marked notification in the local chat thread.

    The message is prefixed with the system marker so the UI renders it as a
    chip and the Mind reads it as an event in the thread (e.g. trend research
    results it can answer grounded in). The thread is initialised first when
    it is empty, mirroring ``send_chat_message``.
    """
    _agent_id()
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
    _agent_id()
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
    _agent_id()
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
        raise MindsError(f"Experiment verdict failed validation: {exc}") from exc


def decide_experiment_winner(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    *,
    chat_context: str | None = None,
    conversation_alias: str | None = None,
) -> ExperimentVerdict:
    """Ask the Mind to pick the winning variant of a concluded experiment.

    The Mind answers in two steps: first an honest prose read — which it gives
    readily even when accumulated context causes refusals on direct JSON
    prompts — then a schema-fill message converting that read into the
    structured verdict. A single-message JSON-only prompt reads as "fabricate
    a verdict" to the Mind and triggers refusals that fail the experiment.

    ``conversation_alias`` isolates this prompt in its own conversation when
    provided, preventing the Mind from accumulating context that causes prose
    replies instead of the structured JSON verdict.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable verdicts, unknown winner ids, empty reasoning) so callers
    can fail the experiment closed instead of falling back to metrics.
    """
    alias = conversation_alias or MESSAGING_ALIAS
    agent_id = _agent_id()
    read_prompt = _build_winner_read_prompt(platform, variants, transcript, chat_context)
    read = _message_mind(agent_id, read_prompt, alias=alias)
    if not isinstance(read, str) or not read.strip():
        raise MindsError("Experiment verdict response missing 'response' text")
    try:
        verdict = _parse_winner_verdict(read)
    except MindsError:
        fill = _build_winner_fill_prompt()
        message = _message_mind(agent_id, fill, alias=alias)
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
