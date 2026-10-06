from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.services.llm import ClipMetadata


class AdaptationSummary(BaseModel):
    platform: str
    surface: str
    status: str
    features: dict[str, Any] | None = None
    assets: dict[str, Any] | None = None


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
    latest_adaptations: list[AdaptationSummary] = []
    created_at: datetime
