from datetime import datetime

from pydantic import BaseModel

from app.services.minds import ClipMetadata


class ClipOut(BaseModel):
    id: str
    job_id: str
    title: str
    start_time: float
    end_time: float
    transcript_text: str
    video_url: str
    thumbnail_url: str | None = None
    virality_score: int | None = None
    suggested_hooks: ClipMetadata | None = None
    created_at: datetime
