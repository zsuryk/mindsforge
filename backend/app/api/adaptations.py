from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.adaptation import AdaptationStatus, ClipAdaptation
from app.models.clip import Clip
from app.models.job import utcnow
from app.schemas.adaptation import (
    SURFACES_BY_PLATFORM,
    AdaptationAssetsOut,
    AdaptationOut,
    AdaptationThumbnailVariantOut,
)
from app.services.adaptations import generate_adaptation
from app.services.media import media_url

router = APIRouter()


def _to_out(adaptation: ClipAdaptation) -> AdaptationOut:
    assets = None
    if adaptation.assets:
        thumbs = [
            AdaptationThumbnailVariantOut(
                id=variant["id"],
                frame_timestamp=variant.get("frame_timestamp") or 0.0,
                overlay_text=variant.get("overlay_text") or "",
                url=media_url(variant.get("file_path")) or "",
            )
            for variant in (adaptation.assets.get("thumbnail_variants") or [])
        ]
        assets = AdaptationAssetsOut(
            thumbnail_variants=thumbs,
            captions_url=media_url(adaptation.assets.get("captions_file")),
            chapters_url=media_url(adaptation.assets.get("chapters_file")),
        )
    return AdaptationOut(
        id=adaptation.id,
        clip_id=adaptation.clip_id,
        platform=adaptation.platform,
        surface=adaptation.surface.value,
        status=adaptation.status,
        features=adaptation.features,
        assets=assets,
        error_message=adaptation.error_message,
        created_at=adaptation.created_at,
        updated_at=adaptation.updated_at,
    )


def _valid_target(platform: str, surface: str) -> bool:
    return surface in SURFACES_BY_PLATFORM.get(platform, [])


@router.get("/clips/{clip_id}/adaptations", response_model=list[AdaptationOut])
def list_adaptations(clip_id: str, db: Session = Depends(get_db)) -> list[AdaptationOut]:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    adaptations = db.scalars(
        select(ClipAdaptation)
        .where(ClipAdaptation.clip_id == clip_id)
        .order_by(ClipAdaptation.created_at)
    ).all()
    return [_to_out(adaptation) for adaptation in adaptations]


@router.post(
    "/clips/{clip_id}/adaptations/{platform}/{surface}",
    response_model=AdaptationOut,
)
def generate_clip_adaptation(
    clip_id: str,
    platform: str,
    surface: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JSONResponse | AdaptationOut:
    """Start lazy generation for a clip platform-surface, or return the
    cached row (READY/PENDING/GENERATING) untouched."""
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    if not _valid_target(platform, surface):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported platform/surface: {platform}/{surface}",
        )

    adaptation = db.scalar(
        select(ClipAdaptation).where(
            ClipAdaptation.clip_id == clip_id,
            ClipAdaptation.platform == platform,
            ClipAdaptation.surface == surface,
        )
    )
    if adaptation is not None:
        if adaptation.status in (
            AdaptationStatus.PENDING,
            AdaptationStatus.GENERATING,
            AdaptationStatus.READY,
        ):
            return JSONResponse(
                content=jsonable_encoder(_to_out(adaptation)), status_code=200
            )
        adaptation.status = AdaptationStatus.PENDING
        adaptation.error_message = None
        adaptation.updated_at = utcnow()
        db.commit()
        db.refresh(adaptation)
    else:
        adaptation = ClipAdaptation(
            clip_id=clip_id, platform=platform, surface=surface
        )
        db.add(adaptation)
        db.commit()
        db.refresh(adaptation)

    background_tasks.add_task(generate_adaptation, adaptation.id)
    return JSONResponse(
        content=jsonable_encoder(_to_out(adaptation)),
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.get(
    "/clips/{clip_id}/adaptations/{adaptation_id}",
    response_model=AdaptationOut,
)
def get_adaptation(
    clip_id: str, adaptation_id: str, db: Session = Depends(get_db)
) -> AdaptationOut:
    adaptation = db.get(ClipAdaptation, adaptation_id)
    if adaptation is None or adaptation.clip_id != clip_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Adaptation not found"
        )
    return _to_out(adaptation)