from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.job import utcnow


class MemoryEntry(Base):
    """A single key/value cell of the Mind's persistent context tree.

    The Minds Builder API no longer persists a memory tree, so it lives
    locally keyed by agent id (see minds.fetch_memory / update_memory).
    """

    __tablename__ = "mind_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "key", name="uq_mind_memory_agent_key"),
    )
