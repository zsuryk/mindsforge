from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_url: str | None = None
    file_path: str | None = None
    status: JobStatus
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus
    message: str