import httpx
import pytest

from app.models.todo import TodoItemType
from app.services import minds, trends
from app.services import todo as todo_module

TAVILY_BODY = {
    "query": "fitness shorts",
    "results": [
        {
            "title": "Best Fitness Shorts",
            "url": "https://example.com/fitness",
            "content": "The best fitness shorts of the season.",
        },
        {
            "title": "Shorts That Last",
            "url": "https://example.com/shorts",
            "content": "Durability test results.",
        },
        {
            "title": "Trend Report",
            "url": "https://example.com/trend",
            "content": "Weekly trend report.",
        },
        {
            "title": "Fourth Hit",
            "url": "https://example.com/fourth",
            "content": "An extra result beyond the notification's top 3.",
        },
    ],
}

TAVILY_BODY_RESULTS = TAVILY_BODY["results"]


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _configure_env(
    monkeypatch: pytest.MonkeyPatch, tavily_key: str = "test-tavily-key"
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    monkeypatch.setenv("TAVILY_API_KEY", tavily_key)
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stub_tavily(
    monkeypatch: pytest.MonkeyPatch, *, body=None, status_code=200, error=None
):
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None, **kwargs):
        calls.append({"url": url, "json": json})
        if error is not None:
            raise error
        if isinstance(body, FakeResponse):
            return body
        return FakeResponse(body, status_code)

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def _stub_chat(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, dict]] = []
    initialised = False

    def fake_post(path, payload):
        nonlocal initialised
        posts.append((path, payload))
        if (
            path == "/v1/messaging/message"
            and payload.get("messageText") == minds.CHAT_INIT_INSTRUCTION
        ):
            initialised = True
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            if initialised:
                return FakeResponse([{"senderType": 1, "messageText": "old row"}], 200)
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "chat reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)
    return posts


def _message_posts(posts: list[tuple[str, dict]]) -> list[dict]:
    return [payload for path, payload in posts if path == "/v1/messaging/message"]


# --- search_trends ---


def test_search_trends_returns_parsed_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    calls = _stub_tavily(monkeypatch, body=TAVILY_BODY)

    results = trends.search_trends("fitness shorts")

    assert len(results) == 4
    assert results[0].title == "Best Fitness Shorts"
    assert results[0].url == "https://example.com/fitness"
    assert results[0].content == "The best fitness shorts of the season."
    request = calls[0]["json"]
    assert request["api_key"] == "test-tavily-key"
    assert request["query"] == "fitness shorts"
    assert request["max_results"] == 5
    assert request["search_depth"] == "basic"
    assert calls[0]["url"] == "https://api.tavily.com/search"


def test_search_trends_raises_naming_key_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch, tavily_key="")

    with pytest.raises(trends.TrendSearchError, match="TAVILY_API_KEY"):
        trends.search_trends("fitness shorts")


def test_search_trends_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, status_code=429)

    with pytest.raises(trends.TrendSearchError, match="status 429"):
        trends.search_trends("fitness shorts")


def test_search_trends_raises_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, error=httpx.ConnectError("connection refused"))

    with pytest.raises(trends.TrendSearchError, match="connection refused"):
        trends.search_trends("fitness shorts")


def test_search_trends_raises_on_non_json_or_unexpected_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=[{"not": "a dict"}])
    with pytest.raises(trends.TrendSearchError, match="unexpected shape"):
        trends.search_trends("fitness shorts")

    class NonJsonResponse(FakeResponse):
        def json(self):
            raise ValueError("not json")

    _stub_tavily(monkeypatch, body=NonJsonResponse("nope"))
    with pytest.raises(trends.TrendSearchError, match="non-JSON"):
        trends.search_trends("fitness shorts")


def test_search_trends_raises_on_non_dict_result_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body={"results": ["not a dict"]})

    with pytest.raises(trends.TrendSearchError, match="unexpected shape"):
        trends.search_trends("fitness shorts")


# --- POST /chat/trends ---


def test_api_chat_trends_researches_persists_and_notifies(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=TAVILY_BODY)
    posts = _stub_chat(monkeypatch)

    test_client, _ = client
    res = test_client.post(
        "/api/v1/chat/trends",
        json={"query": "fitness shorts", "platform": "youtube"},
    )

    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 4
    assert body["results"][0]["title"] == "Best Fitness Shorts"

    memory = test_client.get("/api/v1/agent/memory").json()["memory"]
    history = memory["trend_research"]
    assert len(history) == 1
    entry = history[0]
    assert entry["query"] == "fitness shorts"
    assert entry["platform"] == "youtube"
    assert entry["results"][0]["title"] == "Best Fitness Shorts"
    assert entry["researched_at"]

    rows = minds._chat_rows()
    notification = rows[-1]
    assert notification.role == "system"
    assert notification.text.startswith(minds.SYSTEM_MARKER)
    assert "Researched 'fitness shorts':" in notification.text
    assert (
        "1. Best Fitness Shorts — https://example.com/fitness"
        in notification.text
    )
    assert "2. Shorts That Last" in notification.text
    assert "3. Trend Report" in notification.text
    assert "Fourth Hit" not in notification.text


def test_research_trends_bounds_memory_to_last_10_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=TAVILY_BODY)
    existing = [
        {
            "query": f"old {i}",
            "platform": None,
            "results": [],
            "researched_at": "2026-01-01T00:00:00+00:00",
        }
        for i in range(9)
    ]
    monkeypatch.setattr(
        minds, "fetch_memory", lambda agent_id: {"trend_research": existing}
    )
    monkeypatch.setattr(minds, "post_chat_notification", lambda text: None)
    captured: dict = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: (
            captured.update(agent_id=agent_id, key=key, value=value) or True
        ),
    )

    results = trends.research_trends("fitness shorts")

    assert len(results) == 4
    assert captured["key"] == "trend_research"
    history = captured["value"]
    assert len(history) == 10
    assert history[-1]["query"] == "fitness shorts"
    assert history[0]["query"] == "old 0"


def test_api_chat_trends_502_when_tavily_unconfigured(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch, tavily_key="")

    test_client, _ = client
    res = test_client.post("/api/v1/chat/trends", json={"query": "fitness shorts"})

    assert res.status_code == 502
    assert "TAVILY_API_KEY" in res.json()["detail"]


# --- inline trigger in POST /chat/messages ---


def test_inline_trigger_researches_before_posting_user_message(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch)
    tavily_calls = _stub_tavily(monkeypatch, body=TAVILY_BODY)
    posts = _stub_chat(monkeypatch)

    test_client, _ = client
    res = test_client.post(
        "/api/v1/chat/messages", json={"message": "search trends for fitness shorts"}
    )

    assert res.status_code == 200
    assert res.json()["reply"] == "chat reply"
    assert tavily_calls[0]["json"]["query"] == "fitness shorts"

    messages = _message_posts(posts)
    assert len(messages) == 1
    assert messages[0]["messageText"] == "search trends for fitness shorts"
    rows = minds._chat_rows()
    assert rows[1].text.startswith(minds.SYSTEM_MARKER)
    assert "Researched 'fitness shorts':" in rows[1].text


def test_message_without_trigger_sends_untouched(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch)
    tavily_calls = _stub_tavily(monkeypatch, body=TAVILY_BODY)
    posts = _stub_chat(monkeypatch)

    test_client, _ = client
    res = test_client.post("/api/v1/chat/messages", json={"message": "hello there"})

    assert res.status_code == 200
    assert tavily_calls == []
    messages = _message_posts(posts)
    assert len(messages) == 1
    assert messages[0]["messageText"] == "hello there"


def test_inline_trigger_502_when_tavily_unconfigured(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch, tavily_key="")

    test_client, _ = client
    res = test_client.post(
        "/api/v1/chat/messages", json={"message": "search trends for fitness shorts"}
    )

    assert res.status_code == 502
    assert "TAVILY_API_KEY" in res.json()["detail"]


# --- build_trend_block ---


def _recent_iso(days_ago: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def _entry(query: str, days_ago: int, content: str = "short content") -> dict:
    return {
        "query": query,
        "platform": "youtube",
        "results": [
            {"title": query, "url": f"https://example.com/{query}", "content": content}
        ],
        "researched_at": _recent_iso(days_ago),
    }


def test_build_trend_block_renders_fresh_entries() -> None:
    block = trends.build_trend_block({"trend_research": [_entry("fitness shorts", 1)]})

    assert block is not None
    assert "Trending research (last 7 days):" in block
    assert "fitness shorts" in block
    assert "(youtube)" in block
    assert "https://example.com/fitness shorts" in block


def test_build_trend_block_truncates_long_content() -> None:
    block = trends.build_trend_block(
        {"trend_research": [_entry("fitness shorts", 1, content="x" * 500)]}
    )

    assert block is not None
    assert "…" in block
    for line in block.splitlines():
        assert len(line.strip()) <= 201


def test_build_trend_block_skips_stale_entries() -> None:
    block = trends.build_trend_block({"trend_research": [_entry("fitness shorts", 30)]})

    assert block is None


def test_build_trend_block_accepts_naive_timestamps() -> None:
    from datetime import UTC, datetime, timedelta

    naive = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None).isoformat()
    entry = _entry("fitness shorts", 1)
    entry["researched_at"] = naive

    block = trends.build_trend_block({"trend_research": [entry]})

    assert block is not None
    assert "fitness shorts" in block


def test_build_trend_block_returns_none_without_trend_data() -> None:
    assert trends.build_trend_block({}) is None
    assert trends.build_trend_block({"brand_voice": "bold"}) is None
    assert trends.build_trend_block({"trend_research": []}) is None


def test_build_trend_block_keeps_latest_five_entries() -> None:
    history = [_entry(f"query {i}", 1) for i in range(6)]
    block = trends.build_trend_block({"trend_research": history})

    assert block is not None
    assert "query 0" not in block
    for i in range(1, 6):
        assert f"query {i}" in block


# --- weekly_trend_research — digest TodoItem ---


def test_weekly_trend_research_creates_digest_todo_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=TAVILY_BODY)
    _stub_chat(monkeypatch)
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "update_memory", lambda *a, **kw: True)
    monkeypatch.setattr(
        trends,
        "_build_weekly_digest_body",
        lambda all_results, db=None: ("digest body", "/clips/top", "View top clip"),
    )

    created: list[dict] = []

    def fake_create_todo(type, title, body, action_url=None, action_label=None):
        item = type  # just capture the args
        created.append({"type": type, "title": title, "body": body})
        return item

    monkeypatch.setattr(todo_module, "create_todo", fake_create_todo)

    result = trends.weekly_trend_research()

    assert len(result) == 3
    assert len(created) == 1
    assert created[0]["type"] == TodoItemType.WEEKLY_DIGEST
    assert "Weekly Trend Digest" in created[0]["title"]


def test_weekly_trend_research_no_chat_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that weekly_trend_research does NOT post to chat."""
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=TAVILY_BODY)
    posts = _stub_chat(monkeypatch)
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "update_memory", lambda *a, **kw: True)
    monkeypatch.setattr(
        trends,
        "_build_weekly_digest_body",
        lambda all_results, db=None: ("digest body", None, None),
    )

    def noop_create_todo(*a, **kw):
        return None

    monkeypatch.setattr(todo_module, "create_todo", noop_create_todo)

    trends.weekly_trend_research()

    message_posts = [p for path, p in posts if path == "/v1/messaging/message"]
    # No chat notification should be posted for weekly digests
    assert len(message_posts) == 0


def test_weekly_trend_research_no_digest_when_paused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_tavily(monkeypatch, body=TAVILY_BODY)
    _stub_chat(monkeypatch)
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {"weekly_trends_paused": True})
    monkeypatch.setattr(minds, "update_memory", lambda *a, **kw: True)

    created: list = []

    def fake_create_todo(*args, **kwargs):
        created.append(True)
        return None

    monkeypatch.setattr(todo_module, "create_todo", fake_create_todo)

    result = trends.weekly_trend_research()

    assert result == {}
    assert len(created) == 0


def test_weekly_trend_research_no_digest_when_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    # Stub Tavily to return empty results for all platforms
    empty_body = {"query": "test", "results": []}
    _stub_tavily(monkeypatch, body=empty_body)
    _stub_chat(monkeypatch)
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "update_memory", lambda *a, **kw: True)

    created: list = []

    def fake_create_todo(*args, **kwargs):
        created.append(True)
        return None

    monkeypatch.setattr(todo_module, "create_todo", fake_create_todo)

    trends.weekly_trend_research()

    assert len(created) == 0


# --- _build_weekly_digest_body — full integration ---


def test_build_weekly_digest_body_contains_trends_section(
    monkeypatch: pytest.MonkeyPatch, client
) -> None:
    _configure_env(monkeypatch)
    all_results = {
        "youtube": [
            trends.TrendResult(title="YT Trend 1", url="https://yt1.com", content=""),
            trends.TrendResult(title="YT Trend 2", url="https://yt2.com", content=""),
        ],
        "tiktok": [
            trends.TrendResult(title="TT Trend 1", url="https://tt1.com", content=""),
        ],
    }

    body, action_url, action_label = trends._build_weekly_digest_body(all_results)

    assert "## Top Trending Topics" in body
    assert "YT Trend 1" in body
    assert "YT Trend 2" in body
    assert "TT Trend 1" in body
    assert action_url is None
    assert action_label is None


def test_build_weekly_digest_body_clip_performance(
    monkeypatch: pytest.MonkeyPatch, client
) -> None:
    test_client, _ = client
    _configure_env(monkeypatch)

    # Create a clip directly via the DB
    from app.db.base import get_session_factory
    from app.models.clip import Clip
    from app.models.job import Job

    with get_session_factory()() as db:
        job = Job(source_url="https://example.com/video.mp4", title="Test Job")
        db.add(job)
        db.flush()
        clip = Clip(
            job_id=job.id,
            title="Test Clip",
            start_time=0.0,
            end_time=10.0,
            transcript_text="test transcript",
            file_path="/tmp/test.mp4",
            virality_score=85,
        )
        db.add(clip)
        db.commit()
        clip_id = clip.id

    all_results = {"youtube": [trends.TrendResult(**TAVILY_BODY_RESULTS[0])]}
    body, action_url, action_label = trends._build_weekly_digest_body(all_results)

    assert "## Clip Performance" in body
    assert "Total clips: 1" in body
    assert "Average virality: 85.0" in body
    assert "Top performer: \"Test Clip\"" in body
    assert "virality 85" in body
    assert action_url == f"/clips/{clip_id}"
    assert action_label == "View top clip"


def test_build_weekly_digest_body_suggestions_high_virality(
    monkeypatch: pytest.MonkeyPatch, client
) -> None:
    test_client, _ = client
    _configure_env(monkeypatch)

    from app.db.base import get_session_factory
    from app.models.clip import Clip
    from app.models.job import Job

    with get_session_factory()() as db:
        job = Job(source_url="https://example.com/video2.mp4", title="Hot Job")
        db.add(job)
        db.flush()
        clip = Clip(
            job_id=job.id,
            title="Hot Clip",
            start_time=0.0,
            end_time=10.0,
            transcript_text="test transcript",
            file_path="/tmp/test2.mp4",
            virality_score=92,
        )
        db.add(clip)
        db.commit()

    all_results = {"youtube": [trends.TrendResult(**TAVILY_BODY_RESULTS[0])]}
    body, _, _ = trends._build_weekly_digest_body(all_results)

    assert "## Suggestions" in body
    assert "high-virality" in body
    assert "A/B testing thumbnails" in body


def test_build_weekly_digest_body_suggestions_low_virality(
    monkeypatch: pytest.MonkeyPatch, client
) -> None:
    test_client, _ = client
    _configure_env(monkeypatch)

    from app.db.base import get_session_factory
    from app.models.clip import Clip
    from app.models.job import Job

    with get_session_factory()() as db:
        job = Job(source_url="https://example.com/video3.mp4", title="Weak Job")
        db.add(job)
        db.flush()
        clip = Clip(
            job_id=job.id,
            title="Weak Clip",
            start_time=0.0,
            end_time=10.0,
            transcript_text="test transcript",
            file_path="/tmp/test3.mp4",
            virality_score=15,
        )
        db.add(clip)
        db.commit()

    all_results = {"youtube": [trends.TrendResult(**TAVILY_BODY_RESULTS[0])]}
    body, _, _ = trends._build_weekly_digest_body(all_results)

    assert "## Suggestions" in body
    assert "below 30" in body
    assert "review hooks" in body


def test_build_weekly_digest_body_no_clips(
    monkeypatch: pytest.MonkeyPatch, client
) -> None:
    _configure_env(monkeypatch)

    all_results = {"youtube": [trends.TrendResult(**TAVILY_BODY_RESULTS[0])]}
    body, action_url, action_label = trends._build_weekly_digest_body(all_results)

    assert "## Clip Performance" in body
    assert "No clips scored yet" in body
    assert action_url is None
    assert action_label is None
