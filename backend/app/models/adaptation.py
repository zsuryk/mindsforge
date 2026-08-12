from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.job import utcnow

if TYPE_CHECKING:
    from app.models.clip import Clip


class AdaptationSurface(str, Enum):
    SHORTS = "SHORTS"
    LONG_FORM = "LONG_FORM"
    POST = "POST"


class AdaptationStatus(str, Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"


class ClipAdaptation(Base):
    __tablename__ = "clip_adaptations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    clip_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(32))
    surface: Mapped[AdaptationSurface] = mapped_column(
        SAEnum(
            AdaptationSurface,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    status: Mapped[AdaptationStatus] = mapped_column(
        SAEnum(
            AdaptationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AdaptationStatus.PENDING,
        nullable=False,
    )
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    assets: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    clip: Mapped["Clip"] = relationship()