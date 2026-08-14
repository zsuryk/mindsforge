from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.schemas.experiment import AbActiveOut, AbExperimentOut, AbExperimentStartIn
from app.services.media import media_url

router = APIRouter()

CONCLUDED_RECENCY_DAYS = 7


def _to_out(experiment: AbExperiment) -> AbExperimentOut:
    return AbExperimentOut(
        id=experiment.id,
        clip_id=experiment.clip_id,
        clip_title=experiment.clip.title if experiment.clip else "",
        platform=experiment.platform,
        variant_kind=experiment.variant_kind,
        status=experiment.status,
        variants=[
            {
                "variant_id": variant["variant_id"],
                "title": variant["title"],
                "thumbnail_url": media_url(variant.get("thumbnail_path")),
                "ctr": variant.get("ctr") or 0.0,
                "views": variant.get("views") or 0,
            }
            for variant in (experiment.variants or [])
        ],
        winning_variant_id=experiment.winning_variant_id,
        learned_insight=experiment.learned_insight,
        error_message=experiment.error_message,
        created_at=experiment.created_at,
        concluded_at=experiment.concluded_at,
    )


@router.post(
    "/ab-tests/start",
    status_code=status.HTTP_201_CREATED,
    response_model=AbExperimentOut,
)
def start_ab_test(
    payload: AbExperimentStartIn,
    db: Session = Depends(get_db),
) -> AbExperimentOut:
    clip = db.get(Clip, payload.clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    titles = [title.strip() for title in payload.titles if title and title.strip()]
    variant_titles = titles

    if payload.variant_kind.value == "THUMBNAIL":
        thumbnail_paths = [
            path for path in payload.thumbnail_paths if path and path.strip()
        ]
        if len(set(thumbnail_paths)) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least two distinct thumbnail variants",
            )
        if len(set(titles)) < 2:
            variant_titles = [
                f"Thumbnail {i}" for i in range(1, len(thumbnail_paths) + 1)
            ]
    elif len(set(titles)) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least two distinct variant titles",
        )

    experiment = AbExperiment(
        clip_id=clip.id,
        platform=payload.platform,
        variant_kind=payload.variant_kind,
        status=AbExperimentStatus.ACTIVE,
        variants=[
            {
                "variant_id": str(uuid4()),
                "title": title,
                "thumbnail_path": (
                    thumbnail_paths[index]
                    if payload.variant_kind.value == "THUMBNAIL"
                    else clip.thumbnail_path
                ),
                "ctr": 0.0,
                "views": 0,
                "clicks": 0,
            }
            for index, title in enumerate(variant_titles)
        ],
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return _to_out(experiment)


@router.get("/ab-tests/active", response_model=AbActiveOut)
def list_active_ab_tests(db: Session = Depends(get_db)) -> AbActiveOut:
    recency_cutoff = datetime.now(timezone.utc) - timedelta(days=CONCLUDED_RECENCY_DAYS)
    experiments = db.scalars(
        select(AbExperiment)
        .where(
            or_(
                AbExperiment.status == AbExperimentStatus.ACTIVE,
                and_(
                    AbExperiment.status == AbExperimentStatus.CONCLUDED,
                    AbExperiment.concluded_at >= recency_cutoff,
                ),
            )
        )
        .order_by(AbExperiment.created_at.desc())
    ).all()
    return AbActiveOut(
        view_threshold=get_settings().AB_TEST_VIEW_THRESHOLD,
        experiments=[_to_out(experiment) for experiment in experiments],
    )
