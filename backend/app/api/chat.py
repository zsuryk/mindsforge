import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import (
    ChatHistoryOut,
    ChatSendIn,
    ChatSendOut,
    TrendResearchIn,
    TrendResearchOut,
    WeeklyTrendsStatusOut,
    WeeklyTrendsToggleIn,
)
from app.services import minds, trends

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
    logger.debug("POST /chat/messages: %s", payload.message[:80])
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
    return ChatSendOut(reply=reply)


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


@router.post("/chat/trends/weekly-run", response_model=TrendResearchOut)
def trigger_weekly_trends_run() -> TrendResearchOut:
    try:
        all_results = trends.weekly_trend_research()
    except (trends.TrendSearchError, minds.MindsError) as exc:
        _raise_upstream_error(exc)
    flat = [r for results in all_results.values() for r in results]
    return TrendResearchOut(results=[result.model_dump() for result in flat])


@router.get("/chat/trends/weekly-status", response_model=WeeklyTrendsStatusOut)
def get_weekly_trends_status() -> WeeklyTrendsStatusOut:
    return WeeklyTrendsStatusOut(**trends.get_weekly_trends_status())


@router.post("/chat/trends/weekly-toggle", response_model=WeeklyTrendsStatusOut)
def toggle_weekly_trends(payload: WeeklyTrendsToggleIn) -> WeeklyTrendsStatusOut:
    try:
        status = trends.toggle_weekly_trends(payload.paused)
    except minds.MindsError as exc:
        _raise_upstream_error(exc)
    return WeeklyTrendsStatusOut(**status)
