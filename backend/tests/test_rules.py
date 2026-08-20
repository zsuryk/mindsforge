from typing import Any

import pytest

from app.services import minds, rules
from app.services.rules import BrandRule, RuleExtractionError


class _Completions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, model: str, messages: list[dict[str, str]], **kwargs: Any):
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})
        return _Response(self._content)


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _FakeGroq:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.chat = _Chat("")


def _stub_groq(
    monkeypatch: pytest.MonkeyPatch, content: str = '{"rules": []}'
) -> _Completions:
    completions = _Completions(content)

    class StubGroq(_FakeGroq):
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat = _Chat("")
            self.chat.completions = completions

    monkeypatch.setattr(rules, "Groq", StubGroq)
    return completions


def _stub_exploding_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    class ExplodingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("groq is down")

    class ExplodingChat:
        completions = ExplodingCompletions()

    class ExplodingGroq:
        def __init__(self, api_key: str) -> None:
            pass

        chat = ExplodingChat()

    monkeypatch.setattr(rules, "Groq", ExplodingGroq)


def _configure_env(
    monkeypatch: pytest.MonkeyPatch, groq_key: str = "test-groq-key"
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    monkeypatch.setenv("GROQ_API_KEY", groq_key)
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _ChatResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload


def _stub_chat(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    posts: list[tuple[str, dict]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return _ChatResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return _ChatResponse([], 200)
        return _ChatResponse([{"senderType": 0, "messageText": "chat reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)
    return posts


# --- extract_brand_rules ---


def test_extract_brand_rules_returns_structured_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    completions = _stub_groq(
        monkeypatch,
        '{"rules": ["always use bold captions", "never clickbait"]}',
    )

    extracted = rules.extract_brand_rules(
        "please always use bold captions and never clickbait", platform="youtube"
    )

    assert extracted == [
        BrandRule(text="always use bold captions", platform="youtube"),
        BrandRule(text="never clickbait", platform="youtube"),
    ]
    call = completions.calls[0]
    assert call["model"] == rules.EXTRACTION_MODEL
    assert "always use bold captions" in call["messages"][0]["content"]
    assert call["kwargs"].get("response_format") == {"type": "json_object"}


def test_extract_brand_rules_returns_empty_for_no_preference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(monkeypatch, '{"rules": []}')

    assert rules.extract_brand_rules("what do you think of this clip?") == []


def test_extract_brand_rules_ignores_blank_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(monkeypatch, '{"rules": ["", "   ", "post shorts daily"]}')

    extracted = rules.extract_brand_rules("post shorts daily")

    assert [rule.text for rule in extracted] == ["post shorts daily"]


def test_extract_brand_rules_raises_naming_key_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch, groq_key="")

    with pytest.raises(RuleExtractionError, match="GROQ_API_KEY"):
        rules.extract_brand_rules("hello")


def test_extract_brand_rules_raises_on_groq_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_exploding_groq(monkeypatch)

    with pytest.raises(RuleExtractionError, match="groq is down"):
        rules.extract_brand_rules("hello")


def test_extract_brand_rules_raises_on_non_json_or_unexpected_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(monkeypatch, "not json")
    with pytest.raises(RuleExtractionError, match="non-JSON"):
        rules.extract_brand_rules("hello")

    _stub_groq(monkeypatch, '{"unexpected": "shape"}')
    with pytest.raises(RuleExtractionError, match="unexpected shape"):
        rules.extract_brand_rules("hello")


# --- persist_brand_rules / extract_and_persist_brand_rules ---


def test_extract_and_persist_appends_to_brand_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(
        monkeypatch,
        '{"rules": ["always use bold captions", "post shorts daily"]}',
    )
    monkeypatch.setattr(
        minds, "fetch_memory", lambda agent_id: {"brand_rules": []}
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(agent_id=agent_id, key=key, value=value)
        or True,
    )

    extracted = rules.extract_and_persist_brand_rules("always use bold captions")

    assert [rule.text for rule in extracted] == [
        "always use bold captions",
        "post shorts daily",
    ]
    assert captured["agent_id"] == "agent-1"
    assert captured["key"] == "brand_rules"
    history = captured["value"]
    assert len(history) == 2
    assert history[0]["text"] == "always use bold captions"
    assert history[0]["platform"] is None
    assert history[0]["source"] == "chat"
    assert history[0]["created_at"]
    assert history[1]["text"] == "post shorts daily"


def test_extract_and_persist_no_preference_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(monkeypatch, '{"rules": []}')
    memory_reads: list[str] = []
    memory_writes: list[tuple[str, str, Any]] = []
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: memory_reads.append(agent_id) or {"brand_rules": []},
    )
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: memory_writes.append((agent_id, key, value)) or True,
    )

    assert rules.extract_and_persist_brand_rules("how do I edit this?") == []
    assert memory_reads == []
    assert memory_writes == []


def test_persist_brand_rules_bounds_to_last_50_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    existing = [
        {"text": f"rule {i}", "platform": None, "created_at": "x", "source": "chat"}
        for i in range(49)
    ]
    monkeypatch.setattr(
        minds, "fetch_memory", lambda agent_id: {"brand_rules": existing}
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(agent_id=agent_id, key=key, value=value)
        or True,
    )

    rules.persist_brand_rules(
        "agent-1",
        [BrandRule(text="new rule"), BrandRule(text="newest rule")],
    )

    history = captured["value"]
    assert len(history) == 50
    assert history[0]["text"] == "rule 1"
    assert history[-2]["text"] == "new rule"
    assert history[-1]["text"] == "newest rule"
    assert history[-1]["source"] == "chat"


def test_persist_brand_rules_is_noop_for_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    memory_writes: list[tuple[str, str, Any]] = []
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: memory_writes.append((agent_id, key, value)) or True,
    )

    rules.persist_brand_rules("agent-1", [])

    assert memory_writes == []


def test_extract_and_persist_returns_empty_when_memory_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_env(monkeypatch)
    _stub_groq(monkeypatch, '{"rules": ["post shorts daily"]}')
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(minds.MindsError("db down")),
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        rules.logger,
        "warning",
        lambda message, *args: warnings.append(message % args),
    )

    # The write path is non-blocking: the sidecar must not confirm a save the
    # memory never accepted, so the rules are withheld from the UI.
    assert rules.extract_and_persist_brand_rules("post shorts daily") == []
    assert any("memory write failed" in w for w in warnings)


# --- memory context injection ---


def test_build_memory_context_renders_brand_rules() -> None:
    context = minds.build_memory_context(
        {
            "brand_voice": "bold",
            "brand_rules": [
                {
                    "text": "always use bold captions",
                    "platform": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "source": "chat",
                }
            ],
        }
    )

    assert "brand_rules" in context
    assert "always use bold captions" in context


def test_adaptation_read_prompt_carries_brand_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.services import adaptations

    _configure_env(monkeypatch)
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: {
            "brand_rules": [
                {
                    "text": "never clickbait",
                    "platform": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "source": "chat",
                }
            ]
        },
    )

    context = adaptations._memory_context(get_settings())

    assert context is not None
    assert "brand_rules" in context
    assert "never clickbait" in context
    prompt = minds._build_adaptation_read_prompt(
        {"id": "c1", "title": "t", "start_time": 0, "end_time": 10, "transcript": "x"},
        "youtube",
        "LONG_FORM",
        [{"start": 0, "end": 5, "text": "hi"}],
        context,
    )
    assert "never clickbait" in prompt


# --- API seam ---


def test_api_send_message_keeps_chat_flow_on_extraction_failure(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch)
    _stub_exploding_groq(monkeypatch)
    posts = _stub_chat(monkeypatch)
    warnings: list[str] = []

    from app.api import chat as chat_api

    monkeypatch.setattr(
        chat_api.logger,
        "warning",
        lambda message, *args: warnings.append(message % args),
    )

    test_client, _ = client
    res = test_client.post(
        "/api/v1/chat/messages", json={"message": "post shorts daily"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "chat reply"
    assert body["rules"] == []
    assert any("Brand-rule extraction skipped" in w for w in warnings)
    messages = [payload for path, payload in posts if path == "/v1/messaging/message"]
    assert messages[-1]["messageText"] == "post shorts daily"


def test_api_send_message_returns_empty_rules_when_groq_unconfigured(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch, groq_key="")
    _stub_chat(monkeypatch)

    test_client, _ = client
    res = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert res.status_code == 200
    assert res.json()["rules"] == []