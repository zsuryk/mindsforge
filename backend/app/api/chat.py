import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import (
    ChatHistoryOut,
    ChatSendIn,
    ChatSendOut,
    TrendResearchIn,
    TrendResearchOut,
)
from app.services import minds, rules, trends

logger = logging.getLogger(__name__)

router = APIRouter()


def _raise_upstream_error(exc: Exception) -> None:
    # Fail-closed per ADR-0002: an unconfigured or failing upstream service
    # (Mind or Tavily) surfaces as a 502 with the clear message, never a
    # silent fallback reply.
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
    ) from exc


@router.post("/chat/messages", response_model=ChatSendOut)
def send_chat_message(payload: ChatSendIn) -> ChatSendOut:
    # Inline trend trigger: "search trends for X" runs the search-and-notify
    # before the user message is posted, so the Mind answers grounded in live
    # data in a single round trip. Explicit intent must not silently degrade.
    trigger = trends.TREND_TRIGGER_PATTERN.search(payload.message)
    if trigger:
        try:
            trends.research_trends(trigger.group(1).strip())
        except (trends.TrendSearchError, minds.MindsError) as exc:
            _raise_upstream_error(exc)
    try:
        reply = minds.send_chat_message(payload.message)
    except minds.MindsError as exc:
        _raise_upstream_error(exc)
    # Brand-rule sidecar (non-blocking): a fast Groq call inspects the user
    # message for explicit creator preferences and appends them to memory so
    # every generation prompt carries the rules. A failure never blocks the
    # chat — the Mind itself read the statement in the thread regardless.
    detected: list[str] = []
    try:
        extracted = rules.extract_and_persist_brand_rules(payload.message)
    except rules.RuleExtractionError as exc:
        logger.warning("Brand-rule extraction skipped: %s", exc)
    else:
        detected = [rule.text for rule in extracted]
    return ChatSendOut(reply=reply, rules=detected)


@router.get("/chat/history", response_model=ChatHistoryOut)
def get_chat_history() -> ChatHistoryOut:
    try:
        messages = minds.fetch_chat_history()
    except minds.MindsError as exc:
        _raise_upstream_error(exc)
    return ChatHistoryOut(messages=messages)


@router.post("/chat/trends", response_model=TrendResearchOut)
def research_chat_trends(payload: TrendResearchIn) -> TrendResearchOut:
    try:
        results = trends.research_trends(payload.query, platform=payload.platform)
    except (trends.TrendSearchError, minds.MindsError) as exc:
        _raise_upstream_error(exc)
    return TrendResearchOut(results=[result.model_dump() for result in results])
