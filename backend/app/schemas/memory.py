from typing import Any

from pydantic import BaseModel


class MemoryOut(BaseModel):
    agent_id: str
    memory: dict[str, Any]


class MemoryUpdateIn(BaseModel):
    key: str
    value: Any


class MemoryUpdateOut(BaseModel):
    success: bool
