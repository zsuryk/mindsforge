from sqlalchemy import func, select

from app.db.base import get_session_factory
from app.models.todo import TodoItem, TodoItemType


def create_todo(
    type: TodoItemType,
    title: str,
    body: str,
    action_url: str | None = None,
    action_label: str | None = None,
) -> TodoItem:
    with get_session_factory()() as db:
        item = TodoItem(
            type=type,
            title=title,
            body=body,
            action_url=action_url,
            action_label=action_label,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


def list_todos(
    type: TodoItemType | None = None,
    unread: bool | None = None,
    archived: bool = False,
) -> list[TodoItem]:
    with get_session_factory()() as db:
        stmt = select(TodoItem).where(TodoItem.is_archived == archived)
        if type is not None:
            stmt = stmt.where(TodoItem.type == type)
        if unread is not None:
            stmt = stmt.where(TodoItem.is_read == (not unread))
        stmt = stmt.order_by(TodoItem.created_at.desc())
        return list(db.scalars(stmt).all())


def get_todo(item_id: str) -> TodoItem | None:
    with get_session_factory()() as db:
        return db.get(TodoItem, item_id)


def update_todo(
    item_id: str,
    is_read: bool | None = None,
    is_archived: bool | None = None,
) -> TodoItem | None:
    with get_session_factory()() as db:
        item = db.get(TodoItem, item_id)
        if item is None:
            return None
        if is_read is not None:
            item.is_read = is_read
        if is_archived is not None:
            item.is_archived = is_archived
        db.commit()
        db.refresh(item)
        return item


def mark_read(item_id: str) -> TodoItem | None:
    return update_todo(item_id, is_read=True)


def archive(item_id: str) -> TodoItem | None:
    return update_todo(item_id, is_archived=True)


def unread_count() -> int:
    with get_session_factory()() as db:
        return db.scalar(
            select(func.count()).select_from(TodoItem).where(
                TodoItem.is_archived == False,  # noqa: E712
                TodoItem.is_read == False,  # noqa: E712
            )
        ) or 0
