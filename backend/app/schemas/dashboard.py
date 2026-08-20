from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DashboardStats(BaseModel):
    total_clips: int
    active_ab_tests: int
    avg_virality: float | None = None
    total_insights: int


class MindActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    label: str
    detail: dict[str, Any] | None = None
    ref_id: str | None = None
    created_at: datetime