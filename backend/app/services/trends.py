import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.models.todo import TodoItemType
from app.services import activity, llm, todo

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
HTTP_TIMEOUT_SECONDS = 30.0

TREND_RESEARCH_KEY = "trend_research"
TREND_RESEARCH_MAX_ENTRIES = 20
TREND_NOTIFICATION_RESULTS = 3
TREND_BLOCK_MAX_ENTRIES = 5
TREND_BLOCK_MAX_AGE_DAYS = 7
TREND_BLOCK_CONTENT_CHARS = 200

WEEKLY_TRENDS_LAST_RUN_KEY = "weekly_trends_last_run"
WEEKLY_TRENDS_PAUSED_KEY = "weekly_trends_paused"
WEEKLY_PLATFORM_QUERIES: dict[str, str] = {
    "youtube": "youtube shorts trending this week",
    "tiktok": "tiktok viral trends this week",
    "x": "x twitter trending topics this week",
}

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


def research_trends(
    query: str, platform: str | None = None, *, source: str = "manual"
) -> list[TrendResult]:
    """Search the web and land the results where they matter.

    Runs the search, appends the results to the Mind's `trend_research` memory
    key (bounded to the latest 20 entries), posts a system-marked notification
    to the chat thread so the Mind answers grounded in live data, and returns
    the results for the UI chip.

    Raises TrendSearchError (unconfigured/failing Tavily) or LLMError
    (unconfigured/failing LLM chat) — fail-closed, never silent.
    """
    results = search_trends(query)
    _persist_trend_research(query, platform, results, source=source)
    llm.post_chat_notification(_notification_text(query, results))
    activity.log(
        "trend-researched",
        f"Researched '{query}' — {len(results)} results",
        detail={"platform": platform, "source": source},
    )
    return results


def _persist_trend_research(
    query: str,
    platform: str | None,
    results: list[TrendResult],
    *,
    source: str = "manual",
) -> None:
    memory = llm.fetch_memory()
    history = memory.get(TREND_RESEARCH_KEY)
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "query": query,
            "platform": platform,
            "source": source,
            "results": [result.model_dump() for result in results],
            "researched_at": datetime.now(UTC).isoformat(),
        }
    )
    llm.update_memory(
        TREND_RESEARCH_KEY, history[-TREND_RESEARCH_MAX_ENTRIES:]
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


def _build_weekly_digest_body(
    all_results: dict[str, list[TrendResult]],
    db: Any = None,
) -> tuple[str, str | None, str | None]:
    """Build the weekly digest body, action_url, and action_label.

    Returns a tuple of (body, action_url, action_label).
    """
    lines: list[str] = []

    # --- Trending topics (top 3 across all platforms) ---
    all_trends: list[TrendResult] = []
    for results in all_results.values():
        all_trends.extend(results[:3])
    if all_trends:
        lines.append("## Top Trending Topics")
        for i, trend in enumerate(all_trends[:3], 1):
            lines.append(f"{i}. [{trend.title}]({trend.url})")
        lines.append("")

    # --- Clip performance summary ---
    owns_session = db is None
    if owns_session:
        db = get_session_factory()()
    try:
        total_clips = db.scalar(select(func.count(Clip.id))) or 0
        avg_virality = db.scalar(
            select(func.avg(Clip.virality_score)).where(
                Clip.virality_score.is_not(None)
            )
        )
        top_clip = db.scalars(
            select(Clip)
            .where(Clip.virality_score.is_not(None))
            .order_by(Clip.virality_score.desc())
            .limit(1)
        ).first()

        lines.append("## Clip Performance")
        if total_clips > 0:
            lines.append(f"- Total clips: {total_clips}")
            if avg_virality is not None:
                lines.append(f"- Average virality: {round(avg_virality, 1)}")
            if top_clip:
                lines.append(
                    f"- Top performer: \"{top_clip.title}\" "
                    f"(virality {top_clip.virality_score})"
                )
        else:
            lines.append("- No clips scored yet.")
        lines.append("")

        # --- Actionable suggestions ---
        suggestions: list[str] = []
        if total_clips > 0:
            low_count = db.scalar(
                select(func.count(Clip.id)).where(
                    Clip.virality_score.is_not(None),
                    Clip.virality_score <= 30,
                )
            ) or 0
            high_count = db.scalar(
                select(func.count(Clip.id)).where(
                    Clip.virality_score.is_not(None),
                    Clip.virality_score >= 80,
                )
            ) or 0
            if high_count:
                suggestions.append(
                    f"You have {high_count} high-virality clip(s) — "
                    "consider A/B testing thumbnails to maximize reach."
                )
            if low_count:
                suggestions.append(
                    f"{low_count} clip(s) scored below 30 — "
                    "review hooks or consider re-cutting."
                )
        if not suggestions:
            suggestions.append(
                "Keep creating — the weekly trends will guide your next moves."
            )

        lines.append("## Suggestions")
        for s in suggestions:
            lines.append(f"- {s}")

        body = "\n".join(lines)

        # Link to the best clip if available
        action_url: str | None = None
        action_label: str | None = None
        if top_clip:
            action_url = f"/clips/{top_clip.id}"
            action_label = "View top clip"

        return body, action_url, action_label
    finally:
        if owns_session:
            db.close()


def weekly_trend_research() -> dict[str, list[TrendResult]]:
    """Run trend research for all platforms on the weekly schedule.

    Checks if weekly trends are paused, searches each platform using the
    default queries, persists results with source='weekly', creates a
    weekly_digest TodoItem with a rich summary, and updates the last-run
    timestamp.

    Returns a dict mapping platform name to its results.
    """
    memory = llm.fetch_memory()
    if memory.get(WEEKLY_TRENDS_PAUSED_KEY) is True:
        return {}

    all_results: dict[str, list[TrendResult]] = {}
    for platform, query in WEEKLY_PLATFORM_QUERIES.items():
        try:
            results = search_trends(query)
            _persist_trend_research(query, platform, results, source="weekly")
            all_results[platform] = results
        except TrendSearchError as exc:
            logger.warning("Weekly trend search failed for %s: %s", platform, exc)

    if any(results for results in all_results.values()):
        summary_parts = []
        for platform, results in all_results.items():
            summary_parts.append(f"{platform}: {len(results)} results")
        summary = ", ".join(summary_parts)

        body, action_url, action_label = _build_weekly_digest_body(all_results)
        todo.create_todo(
            type=TodoItemType.WEEKLY_DIGEST,
            title=f"Weekly Trend Digest — {summary}",
            body=body,
            action_url=action_url,
            action_label=action_label,
        )
        activity.log(
            "weekly-trend-research",
            f"Weekly trends — {summary}",
        )

    llm.update_memory(WEEKLY_TRENDS_LAST_RUN_KEY, datetime.now(UTC).isoformat())
    return all_results


def get_weekly_trends_status() -> dict[str, Any]:
    """Return the current status of the weekly trends scheduler."""
    memory = llm.fetch_memory()
    last_run_raw = memory.get(WEEKLY_TRENDS_LAST_RUN_KEY)
    paused = memory.get(WEEKLY_TRENDS_PAUSED_KEY) is True

    last_run: str | None = None
    next_run: str | None = None
    if isinstance(last_run_raw, str):
        last_run = last_run_raw
        try:
            last_dt = datetime.fromisoformat(last_run_raw)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            from app.core.config import get_settings as _gs

            stale = _gs().WEEKLY_TRENDS_STALENESS
            next_dt = last_dt + timedelta(seconds=stale)
            next_run = next_dt.isoformat()
        except ValueError:
            pass

    return {"last_run": last_run, "paused": paused, "next_run": next_run}


def toggle_weekly_trends(paused: bool) -> dict[str, Any]:
    """Enable or disable the weekly trends scheduler."""
    llm.update_memory(WEEKLY_TRENDS_PAUSED_KEY, paused)
    return get_weekly_trends_status()
