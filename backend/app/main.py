import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.ab_tests import router as ab_tests_router
from app.api.adaptations import router as adaptations_router
from app.api.clips import router as clips_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.memory import router as memory_router
from app.core.config import get_settings
from app.db.base import get_session_factory, init_db
from app.models.job import IN_PROGRESS_STATUSES, Job, JobStatus
from app.services import ab_testing

logger = logging.getLogger(__name__)

settings = get_settings()


async def _ab_worker_loop() -> None:
    """Self-improving loop: periodically refresh active experiments and
    conclude any that crossed the view threshold. A failed sweep is logged
    and skipped so the loop keeps running unattended."""
    interval = settings.AB_TEST_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(ab_testing.refresh_active_experiments)
        except Exception as exc:  # noqa: BLE001 - a bad sweep must not kill the loop
            logger.exception("A/B worker sweep failed: %s", exc)


def _recover_orphaned_jobs() -> None:
    """Mark jobs left in an in-progress state by a previous shutdown as FAILED.

    Jobs are processed as in-process background tasks, so any job still
    PENDING/DOWNLOADING/TRANSCRIBING/EXTRACTING_CLIPS at startup was
    interrupted by a restart and will never resume on its own. Recovery is
    skipped when the app does not own processing (PROCESS_JOBS_ON_SUBMIT
    false), since an external worker may still be responsible for them.
    """
    if not get_settings().PROCESS_JOBS_ON_SUBMIT:
        return
    with get_session_factory()() as db:
        orphaned = db.scalars(
            select(Job).where(Job.status.in_(IN_PROGRESS_STATUSES))
        ).all()
        for job in orphaned:
            job.status = JobStatus.FAILED
            job.error_message = "Job interrupted by server restart"
        db.commit()
        if orphaned:
            logger.info("Marked %d interrupted job(s) as failed", len(orphaned))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _recover_orphaned_jobs()
    # Drop any previously-registered /media route (e.g. from a hot reload of
    # this module) before remounting the media directory, so static assets
    # are served fresh from the configured MEDIA_DIR.
    app.router.routes = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) != "/media"
    ]
    app.mount(
        "/media",
        StaticFiles(directory=get_settings().MEDIA_DIR, check_dir=False),
        name="media",
    )
    ab_worker = asyncio.create_task(_ab_worker_loop())
    try:
        yield
    finally:
        ab_worker.cancel()
        try:
            await ab_worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="MindsForge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(jobs_router, prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["jobs"])
app.include_router(clips_router, prefix=settings.API_V1_PREFIX, tags=["clips"])
app.include_router(memory_router, prefix=settings.API_V1_PREFIX, tags=["agent"])
app.include_router(ab_tests_router, prefix=settings.API_V1_PREFIX, tags=["ab-tests"])
app.include_router(adaptations_router, prefix=settings.API_V1_PREFIX, tags=["adaptations"])
app.include_router(dashboard_router, prefix=settings.API_V1_PREFIX, tags=["dashboard"])