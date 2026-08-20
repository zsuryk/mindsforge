import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.services import activity, minds

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
HTTP_TIMEOUT_SECONDS = 30.0

TREND_RESEARCH_KEY = "trend_research"
TREND_RESEARCH_MAX_ENTRIES = 10
TREND_NOTIFICATION_RESULTS = 3
TREND_BLOCK_MAX_ENTRIES = 5
TREND_BLOCK_MAX_AGE_DAYS = 7
TREND_BLOCK_CONTENT_CHARS = 200

# "search for X", "search trends for X", "search trends in X", …
TREND_TRIGGER_PATTERN = re.compile(
    r"search (?:for|trends? in|trends? for) (.+)", re.IGNORECASE
)


class TrendResult(BaseModel):
    title: str
    url: str
    content: str


class TrendSearchError(RuntimeError):
    """Raised when Tavily is unconfigured or a search request/parse fails."""


def search_trends(query: str, max_results: int = 5) -> list[TrendResult]:
    """Search the web via the Tavily API and return the top results.

    Raises TrendSearchError when TAVILY_API_KEY is unconfigured (the message
    names the key) or the request/parse fails — the caller surfaces the clear
    message instead of shipping trend-blind content silently.
    """
    api_key = get_settings().TAVILY_API_KEY
    if not api_key:
        raise TrendSearchError("TAVILY_API_KEY is not configured")
    try:
        response = httpx.post(
            TAVILY_SEARCH_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise TrendSearchError(f"Tavily search request failed: {exc}") from exc
    if response.status_code != 200:
        raise TrendSearchError(
            f"Tavily search failed with status {response.status_code}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise TrendSearchError("Tavily search returned a non-JSON response") from exc
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise TrendSearchError("Tavily search returned an unexpected shape")
    for item in body["results"]:
        if not isinstance(item, dict):
            raise TrendSearchError("Tavily search returned an unexpected shape")
    return [
        TrendResult(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            content=str(item.get("content") or ""),
        )
        for item in body["results"]
    ]


def research_trends(query: str, platform: str | None = None) -> list[TrendResult]:
    """Search the web and land the results where they matter.

    Runs the search, appends the results to the Mind's `trend_research` memory
    key (bounded to the latest 10 entries), posts a system-marked notification
    to the chat thread so the Mind answers grounded in live data, and returns
    the results for the UI chip.

    Raises TrendSearchError (unconfigured/failing Tavily) or MindsError
    (unconfigured/failing Mind chat) — fail-closed, never silent.
    """
    results = search_trends(query)
    agent_id = get_settings().MINDS_AGENT_ID
    if not agent_id:
        raise minds.MindsConfigError("MINDS_AGENT_ID is not configured")
    _persist_trend_research(agent_id, query, platform, results)
    minds.post_chat_notification(_notification_text(query, results))
    activity.log(
        "trend-researched",
        f"Researched '{query}' — {len(results)} results",
        detail={"platform": platform},
    )
    return results


def _persist_trend_research(
    agent_id: str,
    query: str,
    platform: str | None,
    results: list[TrendResult],
) -> None:
    memory = minds.fetch_memory(agent_id)
    history = memory.get(TREND_RESEARCH_KEY)
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "query": query,
            "platform": platform,
            "results": [result.model_dump() for result in results],
            "researched_at": datetime.now(UTC).isoformat(),
        }
    )
    minds.update_memory(
        agent_id, TREND_RESEARCH_KEY, history[-TREND_RESEARCH_MAX_ENTRIES:]
    )


def _notification_text(query: str, results: list[TrendResult]) -> str:
    ranked = " ".join(
        f"{index}. {result.title} — {result.url}"
        for index, result in enumerate(results[:TREND_NOTIFICATION_RESULTS], start=1)
    )
    return f"Researched '{query}': {ranked}"


def build_trend_block(memory: dict[str, Any]) -> str | None:
    """Curated trend research for adaptation prompts.

    Renders the latest 5 `trend_research` entries within the last 7 days, each
    result's content truncated to ~200 chars. Returns None when there is no
    fresh trend data, so existing flows see zero behaviour change.
    """
    history = memory.get(TREND_RESEARCH_KEY)
    if not isinstance(history, list) or not history:
        return None
    cutoff = datetime.now(UTC) - timedelta(days=TREND_BLOCK_MAX_AGE_DAYS)
    fresh: list[dict[str, Any]] = []
    for entry in history:
        researched_at = entry.get("researched_at")
        if not isinstance(researched_at, str):
            continue
        try:
            researched = datetime.fromisoformat(researched_at)
        except ValueError:
            continue
        if researched.tzinfo is None:
            researched = researched.replace(tzinfo=UTC)
        if researched < cutoff:
            continue
        fresh.append(entry)
    if not fresh:
        return None
    lines = ["Trending research (last 7 days):"]
    for entry in fresh[-TREND_BLOCK_MAX_ENTRIES:]:
        results = entry.get("results")
        if not isinstance(results, list) or not results:
            continue
        header = f"- '{entry.get('query', '')}'"
        if entry.get("platform"):
            header += f" ({entry['platform']})"
        if entry.get("researched_at"):
            header += f" researched {entry['researched_at'][:10]}"
        lines.append(f"{header}:")
        for index, result in enumerate(results, start=1):
            content = str(result.get("content") or "")
            if len(content) > TREND_BLOCK_CONTENT_CHARS:
                content = f"{content[:TREND_BLOCK_CONTENT_CHARS]}…"
            lines.append(
                f"  {index}. {result.get('title', '')} — {result.get('url', '')}"
            )
            if content:
                lines.append(f"     {content}")
    return "\n".join(lines)
