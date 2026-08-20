import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.services import minds

logger = logging.getLogger(__name__)

VIEWS_PER_SWEEP_MIN = 10
VIEWS_PER_SWEEP_MAX = 40
LATENT_CTR_MIN = 0.01
LATENT_CTR_MAX = 0.10


def _latent_ctr(variant_id: str) -> float:
    """Deterministic per-variant true click-through rate (fraction, 1%–10%)."""
    seeded = random.Random(variant_id)
    return LATENT_CTR_MIN + seeded.random() * (LATENT_CTR_MAX - LATENT_CTR_MIN)


def _simulate_sweep(variant: dict[str, object], rng: random.Random) -> None:
    """Accumulate one sweep of simulated traffic onto a variant dict.

    New views land uniformly in a small band; clicks follow the variant's
    latent CTR so each variant converges toward its true rate. Cumulative
    clicks are stored alongside views so the reported `ctr` percentage is
    an exact running total, not a reconstruction.
    """
    new_views = rng.randint(VIEWS_PER_SWEEP_MIN, VIEWS_PER_SWEEP_MAX)
    views = int(variant.get("views") or 0) + new_views
    clicks = int(variant.get("clicks") or 0) + sum(
        1
        for _ in range(new_views)
        if rng.random() < _latent_ctr(variant["variant_id"])
    )
    variant["views"] = views
    variant["clicks"] = clicks
    variant["ctr"] = round(clicks / views * 100.0, 2) if views else 0.0


def _fail_experiment(db: Session, experiment: AbExperiment, message: str) -> None:
    """Transition an experiment to FAILED with a stored error message."""
    experiment.status = AbExperimentStatus.FAILED
    experiment.error_message = str(message)[:2048]
    experiment.concluded_at = datetime.now(timezone.utc)
    db.commit()
    logger.warning("Experiment %s failed: %s", experiment.id, experiment.error_message)
    minds.notify_mind(
        f"Experiment {experiment.id} failed: {experiment.error_message}."
    )


def _conclude_experiment(db: Session, experiment: AbExperiment) -> None:
    """Ask the Mind to pick the winner and author the learned insight.

    The verdict call is fail-closed: any MindsError (unconfigured builder,
    network failure, unparseable or invalid verdict) raises so the caller
    can transition the experiment to FAILED — no Python max-CTR fallback.
    """
    clip = experiment.clip
    if clip is None:
        raise RuntimeError("Experiment references a missing clip")
    settings = get_settings()
    memory = None
    if settings.MINDS_AGENT_ID:
        try:
            memory = minds.fetch_memory(settings.MINDS_AGENT_ID)
        except minds.MindsError as exc:
            logger.info(
                "Experiment %s: memory context unavailable, deciding without it: %s",
                experiment.id,
                exc,
            )
    memory_context = minds.build_memory_context(memory) if memory else None
    verdict = minds.decide_experiment_winner(
        platform=experiment.platform,
        variants=[dict(variant) for variant in (experiment.variants or [])],
        transcript=clip.transcript_text,
        memory_context=memory_context,
    )
    experiment.winning_variant_id = verdict.winning_variant_id
    experiment.learned_insight = verdict.reasoning
    experiment.status = AbExperimentStatus.CONCLUDED
    experiment.concluded_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Experiment %s concluded: winner %s", experiment.id, verdict.winning_variant_id
    )
    minds.notify_mind(
        f"Experiment concluded on clip '{clip.title}' ({experiment.platform}). "
        f"Winner: {verdict.winning_variant_id}. Learned insight: "
        f"'{verdict.reasoning}'."
    )


def _persist_insight_to_memory(experiment: AbExperiment) -> None:
    """Append the outcome record to the Mind's `ab_test_history`.

    Best-effort: a missing Minds configuration or a Builder API failure
    leaves the insight persisted locally on the experiment only.
    """
    settings = get_settings()
    if not settings.MINDS_BUILDER_API_KEY or not settings.MINDS_AGENT_ID:
        logger.info(
            "Experiment %s: Minds not configured; insight kept locally", experiment.id
        )
        return
    record = {
        "experiment_id": experiment.id,
        "clip_id": experiment.clip_id,
        "platform": experiment.platform,
        "winning_variant_id": experiment.winning_variant_id,
        "learned_insight": experiment.learned_insight,
        "concluded_at": (
            experiment.concluded_at.isoformat() if experiment.concluded_at else None
        ),
    }
    try:
        memory = minds.fetch_memory(settings.MINDS_AGENT_ID)
        history = memory.get("ab_test_history")
        if not isinstance(history, list):
            history = []
        history.append(record)
        minds.update_memory(settings.MINDS_AGENT_ID, "ab_test_history", history)
        logger.info("Experiment %s: insight written to Minds memory", experiment.id)
    except minds.MindsError as exc:
        logger.warning(
            "Experiment %s: memory write failed, insight kept locally: %s",
            experiment.id,
            exc,
        )


def refresh_active_experiments(
    *,
    rng: random.Random | None = None,
    view_threshold: int | None = None,
) -> list[AbExperiment]:
    """One worker sweep: simulate traffic for every ACTIVE experiment and
    finalize any that crossed the cumulative view threshold.

    Finalization asks the Mind to pick the winner; a Mind failure
    (unconfigured, network, or invalid verdict) fails the experiment
    closed with an error message instead of a max-CTR fallback.
    Returns the finalized experiments (concluded or failed).
    """
    rng = rng or random
    threshold = view_threshold or get_settings().AB_TEST_VIEW_THRESHOLD
    concluded: list[AbExperiment] = []
    with get_session_factory()() as db:
        experiments = db.scalars(
            select(AbExperiment).where(
                AbExperiment.status == AbExperimentStatus.ACTIVE
            )
        ).all()
        for experiment in experiments:
            variants = [dict(variant) for variant in (experiment.variants or [])]
            for variant in variants:
                _simulate_sweep(variant, rng)
            experiment.variants = variants
            db.commit()
            total_views = sum(int(v.get("views") or 0) for v in variants)
            if total_views >= threshold:
                try:
                    _conclude_experiment(db, experiment)
                    _persist_insight_to_memory(experiment)
                except Exception as exc:  # noqa: BLE001 - one broken experiment must not abort the sweep
                    _fail_experiment(db, experiment, exc)
                concluded.append(experiment)
    return concluded
