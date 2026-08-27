from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.todo import (
    TodoCreateIn,
    TodoItemOut,
    TodoListOut,
    TodoUnreadCountOut,
    TodoUpdateIn,
)
from app.services import todo

router = APIRouter()


@router.get("/todos/unread-count", response_model=TodoUnreadCountOut)
def get_unread_count() -> TodoUnreadCountOut:
    return TodoUnreadCountOut(count=todo.unread_count())


@router.get("/todos", response_model=TodoListOut)
def list_todos(
    type: str | None = Query(default=None),
    unread: bool | None = Query(default=None),
    archived: bool = Query(default=False),
) -> TodoListOut:
    from app.models.todo import TodoItemType

    todo_type = None
    if type is not None:
        try:
            todo_type = TodoItemType(type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type: {type}. Must be one of: {[t.value for t in TodoItemType]}",
            )
    items = todo.list_todos(type=todo_type, unread=unread, archived=archived)
    return TodoListOut(
        items=[TodoItemOut.model_validate(i) for i in items],
        unread_count=todo.unread_count(),
    )


@router.post("/todos", response_model=TodoItemOut, status_code=status.HTTP_201_CREATED)
def create_todo(payload: TodoCreateIn) -> TodoItemOut:
    item = todo.create_todo(
        type=payload.type,
        title=payload.title,
        body=payload.body,
        action_url=payload.action_url,
        action_label=payload.action_label,
    )
    return TodoItemOut.model_validate(item)


@router.patch("/todos/{item_id}", response_model=TodoItemOut)
def update_todo(item_id: str, payload: TodoUpdateIn) -> TodoItemOut:
    if payload.is_read is None and payload.is_archived is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of is_read or is_archived must be provided",
        )
    item = todo.update_todo(
        item_id,
        is_read=payload.is_read,
        is_archived=payload.is_archived,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Todo item not found"
        )
    return TodoItemOut.model_validate(item)
