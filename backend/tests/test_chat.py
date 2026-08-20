from typing import Any

import pytest

from app.services import minds


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload


def _configure_minds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _message_posts(posts: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [payload for path, payload in posts if path == "/v1/messaging/message"]


# --- send_chat_message ---


def test_send_chat_message_returns_reply_on_chat_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    posts: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "chat reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    reply = minds.send_chat_message("hello there")

    assert reply == "chat reply"
    # Every post must target the chat conversation, never the scoring alias.
    for _, payload in posts:
        assert payload.get("alias") == minds.CHAT_ALIAS
    assert all(
        payload.get("alias") != minds.MESSAGING_ALIAS for _, payload in posts
    )


def test_send_chat_message_posts_init_instruction_when_conversation_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    posts: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    minds.send_chat_message("first message")

    messages = _message_posts(posts)
    assert len(messages) == 2
    assert messages[0]["messageText"] == minds.CHAT_INIT_INSTRUCTION
    assert messages[0]["messageText"].startswith(minds.SYSTEM_MARKER)
    assert messages[1]["messageText"] == "first message"


def test_send_chat_message_skips_instruction_when_conversation_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    posts: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([{"senderType": 1, "messageText": "old row"}], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    minds.send_chat_message("next message")

    messages = _message_posts(posts)
    assert [message["messageText"] for message in messages] == ["next message"]


def test_send_chat_message_uses_chat_timeout_not_scoring_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chat must fail fast: the deadline uses CHAT_REPLY_TIMEOUT_SECONDS, not
    the generous scoring timeout. If the timeout were wrongly wired to
    MESSAGE_REPLY_TIMEOUT_SECONDS (600s), this test would hang."""
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "CHAT_REPLY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(minds, "MESSAGE_REPLY_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))
    monkeypatch.setattr(
        minds,
        "_get",
        lambda path, params=None: FakeResponse(
            [{"senderType": 1, "messageText": "prompt text"}], 200
        ),
    )

    with pytest.raises(minds.MindsError, match="Timed out"):
        minds.send_chat_message("hello")


def test_send_chat_message_raises_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="not configured"):
        minds.send_chat_message("hello")


# --- fetch_chat_history ---


def test_fetch_chat_history_maps_roles_and_strips_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    rows = [
        {"senderType": 0, "messageText": "Mind says", "fingerprint": "0002_x"},
        {
            "senderType": 1,
            "messageText": "[MindsForge] Experiment concluded",
            "fingerprint": "0003_y",
        },
        {"senderType": 1, "messageText": "creator message", "fingerprint": "0001_z"},
    ]
    monkeypatch.setattr(minds, "_get", lambda path, params=None: FakeResponse(rows, 200))

    messages = minds.fetch_chat_history()

    # Newest-first rows are returned oldest-first for a natural thread.
    assert [message.role for message in messages] == ["user", "mind", "system"]
    assert messages[0].text == "creator message"
    assert messages[1].text == "Mind says"
    assert messages[2].text == "Experiment concluded"
    assert messages[2].fingerprint == "0003_y"


def test_fetch_chat_history_skips_unmarked_sender_type_1_as_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    rows = [
        {"senderType": 1, "messageText": "a follow-up from the creator"},
        {"senderType": 1, "messageText": "[MindsForge] tagged"},
    ]
    monkeypatch.setattr(minds, "_get", lambda path, params=None: FakeResponse(rows, 200))

    messages = minds.fetch_chat_history()

    assert [message.role for message in messages] == ["user", "system"]
    assert messages[0].text == "a follow-up from the creator"
    assert messages[1].text == "tagged"


def test_fetch_chat_history_skips_rows_without_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    rows = [
        {"senderType": 0, "messageText": ""},
        {"senderType": 1, "messageText": "hello", "fingerprint": "0001_a"},
    ]
    monkeypatch.setattr(minds, "_get", lambda path, params=None: FakeResponse(rows, 200))

    assert [message.text for message in minds.fetch_chat_history()] == ["hello"]


def test_fetch_chat_history_raises_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="MINDS_AGENT_ID"):
        minds.fetch_chat_history()


# --- API endpoints ---


def test_api_send_message_returns_reply_and_empty_rules(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_minds(monkeypatch)
    posts: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "hi"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "hi"
    assert body["rules"] == []
    assert all(payload.get("alias") == minds.CHAT_ALIAS for _, payload in posts)


def test_api_send_message_rules_field_populated_by_sidecar_seam(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ticket-17 seam: when the sidecar detects rules, they come back on
    the response for the "saved to your Mind" chip."""
    _configure_minds(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    posts: list[tuple[str, dict[str, Any]]] = []

    class Completions:
        def create(self, model, messages, **kwargs):
            class Message:
                content = '{"rules": ["post shorts daily"]}'

            class Choice:
                message = Message()

            class Response:
                def __init__(self) -> None:
                    self.choices = [Choice()]

            return Response()

    class Chat:
        completions = Completions()

    class FakeGroq:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        chat = Chat()

    from app.services import rules

    monkeypatch.setattr(rules, "Groq", FakeGroq)

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "hi"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    test_client, _ = client
    response = test_client.post(
        "/api/v1/chat/messages", json={"message": "post shorts daily"}
    )

    assert response.status_code == 200
    assert response.json()["rules"] == ["post shorts daily"]


def test_api_send_message_502_on_timeout(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "CHAT_REPLY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(minds, "MESSAGE_REPLY_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))
    monkeypatch.setattr(
        minds,
        "_get",
        lambda path, params=None: FakeResponse(
            [{"senderType": 1, "messageText": "prompt text"}], 200
        ),
    )

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 502
    assert "Timed out" in response.json()["detail"]


def test_api_send_message_502_when_unconfigured(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert response.status_code == 502


def test_api_history_returns_thread(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_minds(monkeypatch)
    rows = [
        {"senderType": 0, "messageText": "mind reply", "fingerprint": "0002_x"},
        {"senderType": 1, "messageText": "creator msg", "fingerprint": "0001_y"},
    ]
    monkeypatch.setattr(minds, "_get", lambda path, params=None: FakeResponse(rows, 200))

    test_client, _ = client
    response = test_client.get("/api/v1/chat/history")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "mind"]
    assert messages[1]["text"] == "mind reply"


def test_api_history_502_when_unconfigured(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    test_client, _ = client
    response = test_client.get("/api/v1/chat/history")

    assert response.status_code == 502