from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.clip import Clip
from app.models.job import Job
from app.schemas.clip import ClipOut
from app.services.media import media_url

router = APIRouter()


def _to_out(clip: Clip) -> ClipOut:
    return ClipOut(
        id=clip.id,
        job_id=clip.job_id,
        title=clip.title,
        start_time=clip.start_time,
        end_time=clip.end_time,
        transcript_text=clip.transcript_text,
        video_url=media_url(clip.file_path) or "",
        thumbnail_url=media_url(clip.thumbnail_path),
        virality_score=clip.virality_score,
        suggested_hooks=clip.suggested_hooks,
        created_at=clip.created_at,
    )


@router.get("/jobs/{job_id}/clips", response_model=list[ClipOut])
def list_job_clips(job_id: str, db: Session = Depends(get_db)) -> list[ClipOut]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    clips = db.scalars(
        select(Clip).where(Clip.job_id == job_id).order_by(Clip.start_time)
    ).all()
    return [_to_out(clip) for clip in clips]


@router.get("/clips/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: str, db: Session = Depends(get_db)) -> ClipOut:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return _to_out(clip)
