from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "mind", "system"]
    text: str
    fingerprint: str | None = None


class ChatSendIn(BaseModel):
    message: str


class ChatSendOut(BaseModel):
    reply: str
    rules: list[str] = Field(default_factory=list)


class ChatHistoryOut(BaseModel):
    messages: list[ChatMessageOut]


class TrendResearchIn(BaseModel):
    query: str
    platform: str | None = None


class TrendResultOut(BaseModel):
    title: str
    url: str
    content: str


class TrendResearchOut(BaseModel):
    results: list[TrendResultOut]
