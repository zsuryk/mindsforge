from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.job import utcnow

if TYPE_CHECKING:
    from app.models.clip import Clip


class AbExperimentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CONCLUDED = "CONCLUDED"
    FAILED = "FAILED"


class AbExperiment(Base):
    __tablename__ = "ab_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    clip_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(64))
    status: Mapped[AbExperimentStatus] = mapped_column(
        SAEnum(
            AbExperimentStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AbExperimentStatus.ACTIVE,
        nullable=False,
    )
    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    winning_variant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    learned_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clip: Mapped["Clip"] = relationship()
