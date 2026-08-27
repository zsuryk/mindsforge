from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_session_factory
from app.models.clip import Clip
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
                TodoItem.is_archived == False,
                TodoItem.is_read == False,
            )
        ) or 0


HIGH_VIRALITY_THRESHOLD = 80
LOW_VIRALITY_THRESHOLD = 30


def generate_clip_suggestions(
    job_id: str, clips: list[Clip], *, db: Session | None = None,
) -> list[TodoItem]:
    """Generate clip suggestion TodoItems based on virality scores.

    - High virality (≥80): suggest A/B testing thumbnails
    - Low virality (≤30): suggest reviewing hooks or re-cutting
    - Multiple clips from same job: suggest cross-platform adaptation
    - Mid-range (31-79): no suggestion to avoid noise
    """
    suggestions: list[TodoItem] = []

    def _create(
        type: TodoItemType,
        title: str,
        body: str,
        action_url: str | None = None,
        action_label: str | None = None,
    ) -> TodoItem:
        if db is not None:
            item = TodoItem(
                type=type,
                title=title,
                body=body,
                action_url=action_url,
                action_label=action_label,
            )
            db.add(item)
            db.flush()
            return item
        return create_todo(type, title, body, action_url, action_label)

    for clip in clips:
        if clip.virality_score is None:
            continue

        if clip.virality_score >= HIGH_VIRALITY_THRESHOLD:
            item = _create(
                type=TodoItemType.CLIP_SUGGESTION,
                title=f"High-performing clip: {clip.title}",
                body=(
                    f"Clip '{clip.title}' scored {clip.virality_score}/100 virality. "
                    "Consider A/B testing different thumbnails to maximize reach."
                ),
                action_url=f"/clips/{clip.id}",
                action_label="View clip",
            )
            suggestions.append(item)

        elif clip.virality_score <= LOW_VIRALITY_THRESHOLD:
            item = _create(
                type=TodoItemType.CLIP_SUGGESTION,
                title=f"Low-performing clip: {clip.title}",
                body=(
                    f"Clip '{clip.title}' scored {clip.virality_score}/100 virality. "
                    "Consider reviewing the hook or re-cutting for better engagement."
                ),
                action_url=f"/clips/{clip.id}",
                action_label="View clip",
            )
            suggestions.append(item)

    if len(clips) > 1:
        item = _create(
            type=TodoItemType.CLIP_SUGGESTION,
            title="Cross-platform adaptation available",
            body=(
                f"Job {job_id} produced {len(clips)} clips. "
                "Consider adapting top performers for different platforms."
            ),
            action_url=f"/jobs/{job_id}",
            action_label="View job",
        )
        suggestions.append(item)

    return suggestions
