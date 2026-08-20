from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatHistoryOut, ChatSendIn, ChatSendOut
from app.services import minds

router = APIRouter()


def _raise_minds_error(exc: minds.MindsError) -> None:
    # Fail-closed per ADR-0002: an unconfigured or failing Mind surfaces as a
    # 502 with the clear message, never a silent fallback reply.
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
    ) from exc


@router.post("/chat/messages", response_model=ChatSendOut)
def send_chat_message(payload: ChatSendIn) -> ChatSendOut:
    try:
        reply = minds.send_chat_message(payload.message)
    except minds.MindsError as exc:
        _raise_minds_error(exc)
    # `rules` is the ticket-17 seam: brand rules extracted from this message.
    return ChatSendOut(reply=reply, rules=[])


@router.get("/chat/history", response_model=ChatHistoryOut)
def get_chat_history() -> ChatHistoryOut:
    try:
        messages = minds.fetch_chat_history()
    except minds.MindsError as exc:
        _raise_minds_error(exc)
    return ChatHistoryOut(messages=messages)