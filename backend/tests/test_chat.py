from typing import Any
from unittest.mock import MagicMock, patch

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
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
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


def test_send_chat_message_persists_init_user_and_reply_rows(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)

    def fake_post(path, payload):
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    minds.send_chat_message("first message")

    history = minds.fetch_chat_history()
    assert [m.role for m in history] == ["system", "user", "mind"]
    assert history[0].text == minds.CHAT_INIT_INSTRUCTION[len(minds.SYSTEM_MARKER):]
    assert history[1].text == "first message"
    assert history[2].text == "reply"


def test_send_chat_message_skips_instruction_when_conversation_nonempty(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    minds._insert_chat_row("user", "old row")

    def fake_post(path, payload):
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([{"senderType": 1, "messageText": "old row"}], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    minds.send_chat_message("next message")

    texts = [m.text for m in minds.fetch_chat_history()]
    assert texts == ["old row", "next message", "reply"]


def test_send_chat_message_uses_chat_timeout_not_scoring_timeout(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
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


def test_send_chat_message_never_invokes_groq_brand_rule_extraction(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)

    def fake_post(path, payload):
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    mock_extract = MagicMock()
    with patch.dict("sys.modules", {"app.services.rules": MagicMock(extract_and_persist_brand_rules=mock_extract)}):
        minds.send_chat_message("always use bold captions")

    mock_extract.assert_not_called()


def test_send_chat_message_never_exposes_groq_client(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)

    def fake_post(path, payload):
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    mock_groq_client = MagicMock()
    mock_groq_class = MagicMock(return_value=mock_groq_client)
    with patch.dict("sys.modules", {"groq": MagicMock(Client=mock_groq_class)}):
        minds.send_chat_message("test message")

    mock_groq_class.assert_not_called()


# --- fetch_chat_history ---


def test_fetch_chat_history_maps_roles_and_strips_marker(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    minds._insert_chat_row("mind", "Mind says")
    minds._insert_chat_row("system", "[MindsForge] Experiment concluded")
    minds._insert_chat_row("user", "creator message")

    messages = minds.fetch_chat_history()

    assert [message.role for message in messages] == ["mind", "system", "user"]
    assert messages[0].text == "Mind says"
    assert messages[1].text == "Experiment concluded"
    assert messages[2].text == "creator message"
    assert messages[2].fingerprint


def test_fetch_chat_history_skips_empty_messages(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    minds._insert_chat_row("mind", "")
    minds._insert_chat_row("user", "hello")

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


def test_api_send_message_returns_reply(
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
    assert all(payload.get("alias") == minds.CHAT_ALIAS for _, payload in posts)


def test_api_send_message_response_has_no_rules_field(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_minds(monkeypatch)

    def fake_post(path, payload):
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "acknowledged"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "always use bold captions"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"reply": "acknowledged"}
    assert "rules" not in body


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
    minds._insert_chat_row("user", "creator msg")
    minds._insert_chat_row("mind", "mind reply")

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
