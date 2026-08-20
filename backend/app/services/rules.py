import json
import logging
from datetime import UTC, datetime

from groq import Groq
from pydantic import BaseModel

from app.core.config import get_settings
from app.services import activity, minds

logger = logging.getLogger(__name__)

BRAND_RULES_KEY = "brand_rules"
BRAND_RULES_MAX_ENTRIES = 50

# Ticket 17 specified llama-3.3-70b-versatile; that model was retired by Groq
# on 2026-08-16 and the documented replacement for it is openai/gpt-oss-120b.
EXTRACTION_MODEL = "openai/gpt-oss-120b"

_EXTRACTION_PROMPT = (
    "You extract explicit brand rules from a creator's message. A brand rule "
    "is an explicit preference about how their content should look, sound, or "
    "be packaged, stated as a directive: 'always use bold captions', 'my "
    "audience is beginners', 'never clickbait', 'post shorts daily'.\n"
    "Ignore questions, opinions, and statements about the clip being discussed. "
    "Only extract explicit creator preference statements, and only when the "
    "message clearly states one.\n"
    'Reply as JSON only: {"rules": ["...", "..."]} or {"rules": []} when no '
    "preference is stated.\n"
    "Creator message:\n{message}"
)


class BrandRule(BaseModel):
    text: str
    platform: str | None = None


class RuleExtractionError(RuntimeError):
    """Raised when brand-rule extraction cannot run (unconfigured/failing Groq).

    A sidecar failure, not a gate: the caller logs it, sends the message to the
    Mind anyway, and returns `rules: []`.
    """


def _parse_rules(text: str, platform: str | None) -> list[BrandRule]:
    """Parse the model's JSON verdict into structured brand rules.

    Raises RuleExtractionError when the reply is not a `{rules: [...]}` object.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuleExtractionError(
            f"Brand-rule extraction returned a non-JSON reply: {text[:200]!r}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise RuleExtractionError(
            f"Brand-rule extraction returned an unexpected shape: {text[:200]!r}"
        )
    rules: list[BrandRule] = []
    for item in data["rules"]:
        if isinstance(item, str) and item.strip():
            rules.append(BrandRule(text=item.strip(), platform=platform))
    return rules


def extract_brand_rules(
    message: str, platform: str | None = None
) -> list[BrandRule]:
    """Run a fast Groq extraction call for explicit creator preferences.

    Returns a structured list of brand rules, or `[]` when the message states
    no explicit preference. Raises RuleExtractionError when GROQ_API_KEY is
    unconfigured (the message names the key) or the call/parse fails.
    """
    api_key = get_settings().GROQ_API_KEY
    if not api_key:
        raise RuleExtractionError("GROQ_API_KEY is not configured")
    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _EXTRACTION_PROMPT.replace("{message}", message),
                }
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise RuleExtractionError(f"Brand-rule extraction failed: {exc}") from exc
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        return []
    return _parse_rules(content, platform)


def persist_brand_rules(agent_id: str, rules: list[BrandRule]) -> None:
    """Append detected rules to the `brand_rules` memory key, bounded to 50.

    Each entry is stored as `{text, platform?, created_at, source: "chat"}`.
    An empty verdict is a no-op (no memory read, no write).
    """
    if not rules:
        return
    memory = minds.fetch_memory(agent_id)
    history = memory.get(BRAND_RULES_KEY)
    if not isinstance(history, list):
        history = []
    for rule in rules:
        history.append(
            {
                "text": rule.text,
                "platform": rule.platform,
                "created_at": datetime.now(UTC).isoformat(),
                "source": "chat",
            }
        )
    minds.update_memory(
        agent_id, BRAND_RULES_KEY, history[-BRAND_RULES_MAX_ENTRIES:]
    )
    for rule in rules:
        activity.log(
            "rule-saved",
            f"'{rule.text}'",
            detail={"platform": rule.platform},
        )


def extract_and_persist_brand_rules(
    message: str, platform: str | None = None
) -> list[BrandRule]:
    """Extract brand rules from a chat message and land them in memory.

    The persistence step is best-effort and non-blocking: any failure is
    logged and `[]` is returned, so the chat stays available when the
    sidecar's write path degrades and the "saved to your Mind" chip never
    confirms a save that did not happen (the Mind itself read the statement
    in the thread regardless). Extraction failures propagate as
    RuleExtractionError — the caller decides to treat them as non-blocking.
    """
    rules = extract_brand_rules(message, platform=platform)
    if not rules:
        return rules
    agent_id = get_settings().MINDS_AGENT_ID
    if not agent_id:
        logger.warning("Brand-rule memory write skipped: MINDS_AGENT_ID is not configured")
        return []
    try:
        persist_brand_rules(agent_id, rules)
    except Exception as exc:  # noqa: BLE001 - any write failure is non-blocking
        logger.warning("Brand-rule memory write failed, rules kept local only: %s", exc)
        return []
    return rules