from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.experiment import (
    AbExperimentDataSource,
    AbExperimentStatus,
    AbExperimentVariantKind,
)

Platform = Literal["youtube_shorts", "youtube", "tiktok", "x"]


class AbExperimentStartIn(BaseModel):
    clip_id: str
    platform: Platform
    titles: list[str] = Field(default_factory=list)
    variant_kind: AbExperimentVariantKind = AbExperimentVariantKind.TITLE
    thumbnail_paths: list[str] = Field(default_factory=list)


class AbVariantMetricsIn(BaseModel):
    views: int = Field(ge=0)
    clicks: int = Field(ge=0)


class AbVariantOut(BaseModel):
    variant_id: str
    title: str
    thumbnail_url: str | None = None
    ctr: float
    views: int
    clicks: int


class AbExperimentOut(BaseModel):
    id: str
    clip_id: str
    clip_title: str
    platform: str
    variant_kind: AbExperimentVariantKind
    status: AbExperimentStatus
    data_source: AbExperimentDataSource
    variants: list[AbVariantOut]
    winning_variant_id: str | None = None
    learned_insight: str | None = None
    error_message: str | None = None
    created_at: datetime
    concluded_at: datetime | None = None


class AbActiveOut(BaseModel):
    view_threshold: int
    experiments: list[AbExperimentOut]
