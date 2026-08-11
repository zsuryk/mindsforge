from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_clips: int
    active_ab_tests: int
    avg_virality: float | None = None
    total_insights: int
