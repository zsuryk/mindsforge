import logging
from dataclasses import asdict
from pathlib import Path

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.job import Job, JobStatus
from app.services import media, transcription

logger = logging.getLogger(__name__)


def run_pipeline(job_id: str) -> None:
    settings = get_settings()
    with get_session_factory()() as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.warning("Job %s not found; skipping pipeline", job_id)
            return
        try:
            if job.source_url:
                job.status = JobStatus.DOWNLOADING
                db.commit()

                raw_dir = settings.MEDIA_DIR / "raw" / job.id
                source_path = media.download_video(job.source_url, raw_dir)
                job.file_path = str(source_path)
                job.status = JobStatus.TRANSCRIBING
                db.commit()
            else:
                job.status = JobStatus.TRANSCRIBING
                db.commit()

            if job.file_path is None:
                raise RuntimeError("No source media available for job")
            source = Path(job.file_path)
            if not source.is_file():
                raise RuntimeError(f"Source media missing: {source}")

            audio_dir = settings.MEDIA_DIR / "audio" / job.id
            audio_dir.mkdir(parents=True, exist_ok=True)
            wav_path = media.extract_audio(source, audio_dir / "audio.wav")
            result = transcription.transcribe(wav_path)
            job.transcript_segments = [asdict(segment) for segment in result.segments]
            job.duration_seconds = result.duration_seconds
            db.commit()
            logger.info(
                "Job %s transcribed: %d segments, %.1fs",
                job.id,
                len(result.segments),
                result.duration_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - any stage failure fails the job
            db.rollback()
            job = db.get(Job, job_id)
            if job is None:
                logger.error("Job %s disappeared during processing", job_id)
                return
            job.status = JobStatus.FAILED
            job.error_message = str(exc)[:2048]
            db.commit()
            logger.info("Job %s failed: %s", job_id, job.error_message)
