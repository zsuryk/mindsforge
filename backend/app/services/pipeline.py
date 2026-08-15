import logging
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.clip import Clip
from app.models.job import Job, JobStatus
from app.services import clips as clips_service
from app.services import media, minds, transcription
from app.services.transcription import TranscriptSegment

logger = logging.getLogger(__name__)


def _extract_clips(db: Session, job: Job, source: Path) -> None:
    """Split the transcript into candidates, cut each into an MP4 with a
    thumbnail frame, and persist a Clip record per candidate."""
    settings = get_settings()
    segments = [
        TranscriptSegment(**segment) for segment in (job.transcript_segments or [])
    ]
    candidates = clips_service.build_clip_candidates(segments)
    if not candidates:
        logger.info("Job %s: no clip candidates from transcript", job.id)
        return

    clips_dir = settings.MEDIA_DIR / "clips" / job.id
    clips_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        clip = Clip(
            id=str(uuid4()),
            job_id=job.id,
            title=candidate.title,
            start_time=candidate.start,
            end_time=candidate.end,
            transcript_text=candidate.transcript_text,
        )
        video_path = clips_dir / f"{clip.id}.mp4"
        thumbnail_path = clips_dir / f"{clip.id}.png"
        media.cut_clip(source, video_path, candidate.start, candidate.end)
        thumbnail_timestamp = candidate.start + min(
            1.0, (candidate.end - candidate.start) / 2
        )
        media.extract_frame_at_timestamp(source, thumbnail_path, thumbnail_timestamp)
        clip.file_path = str(video_path)
        clip.thumbnail_path = str(thumbnail_path)
        db.add(clip)
        logger.info(
            "Job %s: cut clip %s [%.1fs, %.1fs] -> %s",
            job.id,
            clip.id,
            candidate.start,
            candidate.end,
            video_path,
        )


def _score_clips(db: Session, job: Job, conversation_alias: str) -> None:
    """Ask the Mind to score each extracted clip and persist the verdict.

    Scoring is fail-closed (ADR-0002): Minds must be configured and every
    verdict call must succeed, otherwise the job fails. The memory-context
    fetch may still degrade to None — only verdict calls are gated.
    """
    settings = get_settings()
    if not settings.MINDS_BUILDER_API_KEY or not settings.MINDS_AGENT_ID:
        raise minds.MindsConfigError(
            "Minds is not configured (MINDS_BUILDER_API_KEY/MINDS_AGENT_ID); "
            "scoring is fail-closed so the job cannot complete"
        )
    clips = db.scalars(
        select(Clip).where(Clip.job_id == job.id).order_by(Clip.start_time)
    ).all()
    if not clips:
        return

    try:
        memory = minds.fetch_memory(settings.MINDS_AGENT_ID)
    except minds.MindsError as exc:
        logger.info(
            "Job %s: memory context unavailable, scoring without it: %s", job.id, exc
        )
        memory = None
    memory_context = minds.build_memory_context(memory) if memory else None

    for clip in clips:
        metadata = minds.generate_clip_metadata(
            clip.transcript_text,
            duration_seconds=clip.end_time - clip.start_time,
            memory_context=memory_context,
            conversation_alias=conversation_alias,
        )
        clip.virality_score = metadata.virality_score
        clip.suggested_hooks = metadata.model_dump()
        logger.info("Job %s: clip %s scored %d/100", job.id, clip.id, clip.virality_score)


def run_pipeline(job_id: str) -> None:
    settings = get_settings()
    with get_session_factory()() as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.warning("Job %s not found; skipping pipeline", job_id)
            return
        job.error_message = None
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

            job.status = JobStatus.EXTRACTING_CLIPS
            db.commit()
            _extract_clips(db, job, source)
            # Fresh conversation per run: retries re-send identical scoring
            # prompts, and a Mind that sees the same templated prompt repeat in
            # one conversation eventually refuses to answer (surfacing as a
            # non-JSON reply). Isolating each attempt prevents that build-up.
            # The Builder API caps aliases at 64 chars, so the job id is
            # truncated and only the fresh hex keeps the alias unique.
            run_alias = f"{minds.MESSAGING_ALIAS}-{job.id[:8]}-{uuid4().hex}"
            _score_clips(db, job, run_alias)
            job.status = JobStatus.COMPLETED
            db.commit()
            logger.info("Job %s completed with clips extracted", job.id)
        except Exception as exc:  # noqa: BLE001 - any stage failure fails the job
            db.rollback()
            job = db.get(Job, job_id)
            if job is None:
                logger.error("Job %s disappeared during processing", job_id)
                return
            job.status = JobStatus.FAILED
            job.error_message = str(exc)[:2048]
            db.commit()
            logger.error("Job %s failed: %s", job_id, job.error_message)
