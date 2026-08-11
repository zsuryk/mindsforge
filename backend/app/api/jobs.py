from pathlib import Path
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.models.job import IN_PROGRESS_STATUSES, Job
from app.schemas.job import JobCreated, JobOut
from app.services.pipeline import run_pipeline

router = APIRouter()

DUPLICATE_MESSAGE = "A job for this URL is already being processed"


def _uploads_dir() -> Path:
    path = get_settings().MEDIA_DIR / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_source_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_url must be a valid http(s) URL",
        )


@router.post("/process", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreated)
def process_job(
    background_tasks: BackgroundTasks,
    source_url: str | None = Form(default=None),
    title: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> JobCreated:
    if (source_url is None) == (file is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of source_url or a file upload",
        )

    job = Job()
    if source_url is not None:
        _validate_source_url(source_url)
        duplicate = db.scalar(
            select(Job).where(
                Job.source_url == source_url,
                Job.status.in_(IN_PROGRESS_STATUSES),
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DUPLICATE_MESSAGE,
            )
        job.source_url = source_url
        job.title = title or source_url
    else:
        assert file is not None
        original_name = Path(file.filename or "upload").name
        job.title = title or original_name

    db.add(job)
    db.flush()

    if file is not None:
        saved_path = _uploads_dir() / f"{job.id}-{Path(file.filename or 'upload').name}"
        saved_path.write_bytes(file.file.read())
        job.file_path = str(saved_path)

    db.commit()
    db.refresh(job)

    if get_settings().PROCESS_JOBS_ON_SUBMIT:
        background_tasks.add_task(run_pipeline, job.id)

    return JobCreated(job_id=job.id, status=job.status, message=f"Job {job.id} accepted for processing")


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return list(db.scalars(select(Job).order_by(Job.created_at.desc())))


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job