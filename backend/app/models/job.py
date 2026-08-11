from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    EXTRACTING_CLIPS = "EXTRACTING_CLIPS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


IN_PROGRESS_STATUSES = {
    JobStatus.PENDING,
    JobStatus.DOWNLOADING,
    JobStatus.TRANSCRIBING,
    JobStatus.EXTRACTING_CLIPS,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=JobStatus.PENDING,
        nullable=False,
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    transcript_segments: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )