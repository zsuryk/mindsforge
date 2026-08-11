from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.schemas.dashboard import DashboardStats

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    total_clips = db.scalar(select(func.count(Clip.id))) or 0
    active_ab_tests = (
        db.scalar(
            select(func.count(AbExperiment.id)).where(
                AbExperiment.status == AbExperimentStatus.ACTIVE
            )
        )
        or 0
    )
    avg_virality = db.scalar(
        select(func.avg(Clip.virality_score)).where(Clip.virality_score.is_not(None))
    )
    total_insights = (
        db.scalar(
            select(func.count(AbExperiment.id)).where(
                AbExperiment.learned_insight.is_not(None)
            )
        )
        or 0
    )
    return DashboardStats(
        total_clips=total_clips,
        active_ab_tests=active_ab_tests,
        avg_virality=round(avg_virality, 1) if avg_virality is not None else None,
        total_insights=total_insights,
    )
