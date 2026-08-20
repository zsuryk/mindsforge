import httpx
import pytest

from app.services import minds, trends

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

    messages = _message_posts(posts)
    notification = messages[-1]
    assert notification["alias"] == minds.CHAT_ALIAS
    assert notification["messageText"].startswith(minds.SYSTEM_MARKER)
    assert "Researched 'fitness shorts':" in notification["messageText"]
    assert (
        "1. Best Fitness Shorts — https://example.com/fitness"
        in notification["messageText"]
    )
    assert "2. Shorts That Last" in notification["messageText"]
    assert "3. Trend Report" in notification["messageText"]
    assert "Fourth Hit" not in notification["messageText"]


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
    assert len(messages) == 3
    assert messages[1]["messageText"].startswith(minds.SYSTEM_MARKER)
    assert "Researched 'fitness shorts':" in messages[1]["messageText"]
    # The user's message is posted untouched, after the notification.
    assert messages[2]["messageText"] == "search trends for fitness shorts"


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
    assert messages[-1]["messageText"] == "hello there"


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
