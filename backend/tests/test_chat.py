from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import llm


def _configure_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stub_completion(monkeypatch: pytest.MonkeyPatch, *replies: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    pending = list(replies) or ["chat reply"]

    def fake_post(url, headers=None, json=None, timeout=None, **_kwargs):
        requests.append({"url": url, "json": json})
        content = pending.pop(0) if len(pending) > 1 else pending[0]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    return requests


# --- send_chat_message ---


def test_send_chat_message_returns_reply_on_chat_alias(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    _stub_completion(monkeypatch, "chat reply")

    assert llm.send_chat_message("hello there") == "chat reply"


def test_send_chat_message_persists_init_user_and_reply_rows(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    requests = _stub_completion(monkeypatch, "reply")

    llm.send_chat_message("first message")

    history = llm.fetch_chat_history()
    assert [m.role for m in history] == ["system", "user", "mind"]
    assert history[0].text == llm.CHAT_INIT_INSTRUCTION[len(llm.SYSTEM_MARKER) :]
    assert history[1].text == "first message"
    assert history[2].text == "reply"
    # The whole stored thread is replayed as the prompt.
    sent = requests[0]["json"]["messages"]
    assert [message["role"] for message in sent] == ["system", "user"]
    assert sent[-1]["content"] == "first message"


def test_send_chat_message_skips_instruction_when_conversation_nonempty(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    llm._insert_chat_row("user", "old row")
    _stub_completion(monkeypatch, "reply")

    llm.send_chat_message("next message")

    texts = [m.text for m in llm.fetch_chat_history()]
    assert texts == ["old row", "next message", "reply"]


def test_send_chat_message_raises_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(llm.LLMConfigError, match="OPENAI_BASE_URL"):
        llm.send_chat_message("hello")


def test_send_chat_message_surfaces_transport_failure(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(llm.LLMError, match="connection refused"):
        llm.send_chat_message("hello")


def test_send_chat_message_never_invokes_groq_brand_rule_extraction(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    _stub_completion(monkeypatch, "reply")

    mock_extract = MagicMock()
    with patch.dict(
        "sys.modules",
        {"app.services.rules": MagicMock(extract_and_persist_brand_rules=mock_extract)},
    ):
        llm.send_chat_message("always use bold captions")

    mock_extract.assert_not_called()


def test_send_chat_message_never_exposes_groq_client(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    _stub_completion(monkeypatch, "reply")

    mock_groq_client = MagicMock()
    mock_groq_class = MagicMock(return_value=mock_groq_client)
    with patch.dict("sys.modules", {"groq": MagicMock(Client=mock_groq_class)}):
        llm.send_chat_message("test message")

    mock_groq_class.assert_not_called()


# --- fetch_chat_history ---


def test_fetch_chat_history_maps_roles_and_strips_marker(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    llm._insert_chat_row("mind", "Mind says")
    llm._insert_chat_row("system", "[MindsForge] Experiment concluded")
    llm._insert_chat_row("user", "creator message")

    messages = llm.fetch_chat_history()

    assert [message.role for message in messages] == ["mind", "system", "user"]
    assert messages[0].text == "Mind says"
    assert messages[1].text == "Experiment concluded"
    assert messages[2].text == "creator message"
    assert messages[2].fingerprint


def test_fetch_chat_history_skips_empty_messages(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    llm._insert_chat_row("mind", "")
    llm._insert_chat_row("user", "hello")

    assert [message.text for message in llm.fetch_chat_history()] == ["hello"]


# --- API endpoints ---


def test_api_send_message_returns_reply(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    _stub_completion(monkeypatch, "hi")

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "hi"}


def test_api_send_message_response_has_no_rules_field(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    _stub_completion(monkeypatch, "acknowledged")

    test_client, _ = client
    response = test_client.post(
        "/api/v1/chat/messages", json={"message": "always use bold captions"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"reply": "acknowledged"}
    assert "rules" not in body


def test_api_send_message_502_on_llm_failure(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None, **_kwargs):
        return httpx.Response(500, json={"error": "boom"})

    monkeypatch.setattr(httpx, "post", fake_post)

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 502
    assert "500" in response.json()["detail"]


def test_api_send_message_502_when_unconfigured(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    test_client, _ = client
    response = test_client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert response.status_code == 502


def test_api_history_returns_thread(
    client: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    llm._insert_chat_row("user", "creator msg")
    llm._insert_chat_row("mind", "mind reply")

    test_client, _ = client
    response = test_client.get("/api/v1/chat/history")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "mind"]
    assert messages[1]["text"] == "mind reply"
