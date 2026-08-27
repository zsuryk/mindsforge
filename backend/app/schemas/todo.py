from datetime import datetime

from pydantic import BaseModel

from app.models.todo import TodoItemType


class TodoItemOut(BaseModel):
    id: str
    type: TodoItemType
    title: str
    body: str
    action_url: str | None
    action_label: str | None
    is_read: bool
    is_archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TodoListOut(BaseModel):
    items: list[TodoItemOut]
    unread_count: int


class TodoCreateIn(BaseModel):
    type: TodoItemType
    title: str
    body: str
    action_url: str | None = None
    action_label: str | None = None


class TodoUpdateIn(BaseModel):
    is_read: bool | None = None
    is_archived: bool | None = None


class TodoUnreadCountOut(BaseModel):
    count: int
