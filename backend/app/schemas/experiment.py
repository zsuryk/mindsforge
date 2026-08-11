from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.experiment import AbExperimentStatus

Platform = Literal["youtube_shorts", "tiktok", "x"]


class AbExperimentStartIn(BaseModel):
    clip_id: str
    platform: Platform
    titles: list[str] = Field(min_length=2)


class AbVariantOut(BaseModel):
    variant_id: str
    title: str
    thumbnail_url: str | None = None
    ctr: float
    views: int


class AbExperimentOut(BaseModel):
    id: str
    clip_id: str
    clip_title: str
    platform: str
    status: AbExperimentStatus
    variants: list[AbVariantOut]
    winning_variant_id: str | None = None
    learned_insight: str | None = None
    created_at: datetime
    concluded_at: datetime | None = None


class AbActiveOut(BaseModel):
    view_threshold: int
    experiments: list[AbExperimentOut]
