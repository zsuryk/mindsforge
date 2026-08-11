from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class TranscriptSegment(BaseModel):
    text: str
    start: float
    end: float


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_url: str | None = None
    file_path: str | None = None
    status: JobStatus
    duration_seconds: float | None = None
    transcript_segments: list[TranscriptSegment] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus
    message: str