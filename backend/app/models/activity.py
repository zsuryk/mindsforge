from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.job import utcnow


class MindActivity(Base):
    """One row of the Mind's visible work log.

    Every Mind-touching service logs a row here (scoring, experiment sweeps,
    conclusions, adaptations, trend research, chat), so the background worker
    becomes a visible 24/7 heartbeat on the dashboard. The table is trimmed
    to the newest 500 rows on every insert (see services.activity.log).
    """

    __tablename__ = "mind_activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)