from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.adaptation import AdaptationStatus

Platform = Literal["youtube", "tiktok", "x"]
Surface = Literal["SHORTS", "LONG_FORM", "POST"]

SURFACES_BY_PLATFORM: dict[str, list[Surface]] = {
    "youtube": ["SHORTS", "LONG_FORM"],
    "tiktok": ["POST"],
    "x": ["POST"],
}


class AdaptationThumbnailVariantOut(BaseModel):
    id: str
    frame_timestamp: float
    overlay_text: str
    url: str


class AdaptationAssetsOut(BaseModel):
    thumbnail_variants: list[AdaptationThumbnailVariantOut] = []
    captions_url: str | None = None
    chapters_url: str | None = None


class AdaptationOut(BaseModel):
    id: str
    clip_id: str
    platform: str
    surface: Surface
    status: AdaptationStatus
    features: dict[str, Any] | None = None
    assets: AdaptationAssetsOut | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime