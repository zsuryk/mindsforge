from typing import Any

import httpx
import pytest

from app.services import llm


def test_send_chat_message_returns_reply(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("chat reply")

    assert llm.send_chat_message("hello there") == "chat reply"


def test_send_chat_message_persists_init_user_and_reply_rows(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("reply")

    llm.send_chat_message("first message")

    history = llm.fetch_chat_history()
    assert [m.role for m in history] == ["system", "user", "mind"]
    assert history[0].text == llm.CHAT_INIT_INSTRUCTION[len(llm.SYSTEM_MARKER) :]
    assert history[1].text == "first message"
    assert history[2].text == "reply"
    # The whole stored thread is replayed as the prompt, oldest first.
    assert llm_http.roles(0) == ["system", "user"]
    assert llm_http.prompt(0, 0) == llm.CHAT_INIT_INSTRUCTION[len(llm.SYSTEM_MARKER) :]
    assert llm_http.prompt(0, 1) == "first message"


def test_send_chat_message_skips_instruction_when_thread_nonempty(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("user", "old row")
    llm_http.reply_with("reply")

    llm.send_chat_message("next message")

    assert [m.text for m in llm.fetch_chat_history()] == ["old row", "next message", "reply"]


def test_send_chat_message_replays_notifications_and_prior_replies(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    """Stored mind turns map to assistant and notifications to system, so the
    model sees the whole thread as one conversation."""
    configure_llm()
    llm.post_chat_notification("Trend results for 'ai video'")
    llm._insert_chat_row("mind", "earlier reply")
    llm_http.reply_with("latest reply")

    llm.send_chat_message("next message")

    assert llm_http.roles(0) == ["system", "system", "assistant", "user"]
    # The UI-only marker is not sent to the model.
    assert llm_http.prompt(0, 1) == "Trend results for 'ai video'"


def test_send_chat_message_raises_when_unconfigured(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm(base_url="")

    with pytest.raises(llm.LLMConfigError, match="OPENAI_BASE_URL"):
        llm.send_chat_message("hello")
    # Fail-closed: nothing was written to the thread.
    assert llm_http.requests == []


def test_send_chat_message_raises_when_api_key_missing(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm("https://api.openai.com/v1", "")

    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm.send_chat_message("hello")
    assert llm_http.requests == []


def test_send_chat_message_surfaces_transport_failure(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ConnectError("connection refused"))

    with pytest.raises(llm.LLMError, match="connection refused"):
        llm.send_chat_message("hello")


def test_send_chat_message_maps_error_status_to_502(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.completions_status_is(500).reply_with("boom")
    test_client, _ = client

    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 502
    assert "500" in response.json()["detail"]


def test_send_chat_message_never_invokes_brand_rule_extraction(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    """Brand rules are extracted by the model via its own memory, not by a
    separate extraction call."""
    from unittest.mock import MagicMock, patch

    configure_llm()
    llm_http.reply_with("reply")

    mock_extract = MagicMock()
    with patch.dict(
        "sys.modules",
        {"app.services.rules": MagicMock(extract_and_persist_brand_rules=mock_extract)},
    ):
        llm.send_chat_message("always use bold captions")

    mock_extract.assert_not_called()


# --- fetch_chat_history ---


def test_fetch_chat_history_maps_roles_and_strips_marker(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
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
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("mind", "")
    llm._insert_chat_row("user", "hello")

    assert [message.text for message in llm.fetch_chat_history()] == ["hello"]


def test_fetch_chat_history_returns_newest_rows_within_limit(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    for i in range(5):
        llm._insert_chat_row("user", f"message {i}")

    messages = llm.fetch_chat_history(limit=2)

    assert [message.text for message in messages] == ["message 3", "message 4"]


# --- API endpoints ---


def test_api_send_message_returns_reply(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("hi")
    test_client, _ = client

    response = test_client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "hi"}


def test_api_send_message_response_has_no_rules_field(
    client: tuple[Any, Any], configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("acknowledged")
    test_client, _ = client

    response = test_client.post(
        "/api/v1/chat/messages", json={"message": "always use bold captions"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"reply": "acknowledged"}
    assert "rules" not in body


def test_api_send_message_502_when_unconfigured(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm(base_url="")
    test_client, _ = client

    response = test_client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert response.status_code == 502


def test_api_history_returns_thread(client: tuple[Any, Any], configure_llm: Any) -> None:
    configure_llm()
    llm._insert_chat_row("user", "creator msg")
    llm._insert_chat_row("mind", "mind reply")
    test_client, _ = client

    response = test_client.get("/api/v1/chat/history")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "mind"]
    assert messages[1]["text"] == "mind reply"
