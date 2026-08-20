import logging
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.base import get_session_factory
from app.models.activity import MindActivity

logger = logging.getLogger(__name__)

ACTIVITY_MAX_ROWS = 500
LABEL_MAX_CHARS = 255


def log(
    event_type: str,
    label: str,
    detail: dict[str, Any] | None = None,
    ref_id: str | None = None,
) -> None:
    """Append one row to the Mind's activity log and trim to the newest 500.

    Observability, not a gate: any failure (database down, oversized value)
    is logged and swallowed so logging never raises into a Mind-touching
    service. The label is truncated to the column width.
    """
    try:
        with get_session_factory()() as db:
            db.add(
                MindActivity(
                    id=str(uuid4()),
                    event_type=event_type,
                    label=label[:LABEL_MAX_CHARS],
                    detail=detail,
                    ref_id=ref_id,
                )
            )
            db.flush()
            newest = (
                select(MindActivity.id)
                .order_by(MindActivity.created_at.desc(), MindActivity.id.desc())
                .limit(ACTIVITY_MAX_ROWS)
            )
            db.execute(delete(MindActivity).where(MindActivity.id.not_in(newest)))
            db.commit()
    except Exception as exc:  # noqa: BLE001 - logging must never raise into callers
        logger.warning("Activity log write failed: %s", exc)