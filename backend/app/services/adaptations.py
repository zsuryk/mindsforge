import logging
from dataclasses import asdict
from uuid import uuid4

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.adaptation import AdaptationStatus, ClipAdaptation
from app.models.todo import TodoItemType
from app.services import activity, minds, todo as todo_module
from app.services.adaptation_assets import render_adaptation_assets
from app.services.transcription import TranscriptSegment

logger = logging.getLogger(__name__)

# Feature-manifest keys in a fixed order, labelled for the chat notification's
# brief summary so the Mind sees at a glance what a READY adaptation contains.
_FEATURE_SUMMARY_LABELS: tuple[tuple[str, str], ...] = (
    ("chapters", "chapters"),
    ("tags", "tags"),
    ("poll", "a poll"),
    ("quiz", "a quiz"),
    ("thumbnail_briefs", "thumbnail briefs"),
    ("shorts_link", "a shorts link"),
    ("platform_hooks", "platform hooks"),
    ("overlay_spec", "overlays"),
    ("caption_style", "captions"),
    ("stickers", "stickers"),
    ("pinned_comment", "a pinned comment"),
    ("caption", "a caption"),
    ("hashtags", "hashtags"),
)


def _feature_summary(features: dict[str, object] | None) -> str:
    """A brief human summary of the feature manifest for the notification."""
    if not features:
        return "feature manifest"
    labels: list[str] = []
    for key, label in _FEATURE_SUMMARY_LABELS:
        value = features.get(key)
        # An empty manifest entry means that feature was not produced, so it
        # must not appear in the summary ("0 thumbnail briefs" is a lie).
        if not value:
            continue
        if key == "thumbnail_briefs" and isinstance(value, list):
            labels.append(f"{len(value)} {label}")
        else:
            labels.append(label)
    return ", ".join(labels) if labels else "feature manifest"


def _chat_context() -> str | None:
    """Best-effort chat context from the Mind's conversation thread.

    Trend data is included automatically — trend research results are posted
    as system notifications in the chat thread, so they appear in the
    conversation context via ``build_chat_context()``.
    """
    return minds.build_chat_context()


def _persist_adaptation_history(adaptation: ClipAdaptation) -> None:
    """Append a per-surface record to the Mind's `adaptation_history`.

    Best-effort (mirrors `ab_test_history`): a memory write failure leaves
    the adaptation READY with features stored locally only.
    """
    settings = get_settings()
    if not settings.MINDS_BUILDER_API_KEY or not settings.MINDS_AGENT_ID:
        return
    record = {
        "adaptation_id": adaptation.id,
        "clip_id": adaptation.clip_id,
        "platform": adaptation.platform,
        "surface": adaptation.surface.value,
        "features": adaptation.features,
        "generated_at": adaptation.updated_at.isoformat() if adaptation.updated_at else None,
    }
    try:
        memory = minds.fetch_memory(settings.MINDS_AGENT_ID)
        history = memory.get("adaptation_history")
        if not isinstance(history, list):
            history = []
        history.append(record)
        minds.update_memory(settings.MINDS_AGENT_ID, "adaptation_history", history)
        logger.info(
            "Adaptation %s: history written to Minds memory", adaptation.id
        )
    except minds.MindsError as exc:
        logger.warning(
            "Adaptation %s: memory write failed, history kept locally: %s",
            adaptation.id,
            exc,
        )


def generate_adaptation(adaptation_id: str) -> None:
    """Lazy generation task for one adaptation row.

    Transitions PENDING → GENERATING → READY (manifest accepted, memory
    history appended) or → FAILED with a stored error message on any
    Minds failure or unexpected error.
    """
    with get_session_factory()() as db:
        adaptation = db.get(ClipAdaptation, adaptation_id)
        if adaptation is None or adaptation.status != AdaptationStatus.PENDING:
            return
        adaptation.status = AdaptationStatus.GENERATING
        db.commit()
        try:
            clip = adaptation.clip
            if clip is None:
                raise RuntimeError("Adaptation references a missing clip")
            segments = [
                TranscriptSegment(**segment)
                for segment in (clip.job.transcript_segments or [])
            ]
            manifest = minds.generate_adaptation_features(
                clip={
                    "id": clip.id,
                    "title": clip.title,
                    "start_time": clip.start_time,
                    "end_time": clip.end_time,
                    "transcript": clip.transcript_text,
                },
                platform=adaptation.platform,
                surface=adaptation.surface.value,
                segments=[asdict(segment) for segment in segments],
                chat_context=_chat_context(),
                # Fresh conversation per attempt: retries re-send byte-identical
                # prompts, and a Mind that sees the same templated prompt repeat
                # in one conversation eventually refuses in prose (ADR-0002).
                # The Builder API caps aliases at 64 chars, so the adaptation id
                # is truncated and only the fresh hex keeps the alias unique.
                conversation_alias=(
                    f"{minds.MESSAGING_ALIAS}-adapt-{adaptation.id[:8]}-{uuid4().hex}"
                ),
            )
            adaptation.features = manifest.model_dump(exclude={"platform", "surface"})
            db.commit()
            adaptation.assets = render_adaptation_assets(adaptation)
            db.commit()
            adaptation.status = AdaptationStatus.READY
            db.commit()
            # Memory history is appended only after the row is committed READY,
            # so the record never claims success for a still-GENERATING row.
            _persist_adaptation_history(adaptation)
            minds.notify_mind(
                f"Adaptation ready: '{clip.title}' for {adaptation.platform}/"
                f"{adaptation.surface.value} — {_feature_summary(adaptation.features)}."
            )
            todo_module.create_todo(
                type=TodoItemType.EXPERIMENT_RESULT,
                title=f"Adaptation ready: '{clip.title}' for {adaptation.platform}/{adaptation.surface.value}",
                body=_feature_summary(adaptation.features),
                action_url=f"/clips/{clip.id}/adaptations/{adaptation.id}",
                action_label="View adaptation",
            )
            logger.info(
                "Adaptation %s ready: %s/%s",
                adaptation.id,
                adaptation.platform,
                adaptation.surface.value,
            )
            activity.log(
                "adaptation-ready",
                f"Adaptation ready: '{clip.title}' for "
                f"{adaptation.platform}/{adaptation.surface.value}",
                ref_id=adaptation.id,
            )
        except Exception as exc:  # noqa: BLE001 - any failure fails the adaptation closed
            adaptation.status = AdaptationStatus.FAILED
            adaptation.error_message = str(exc)[:2048]
            db.commit()
            logger.warning("Adaptation %s failed: %s", adaptation.id, adaptation.error_message)
            activity.log(
                "adaptation-failed",
                f"Adaptation failed: '{clip.title if clip else adaptation.id}' — "
                f"{adaptation.error_message}",
                ref_id=adaptation.id,
            )