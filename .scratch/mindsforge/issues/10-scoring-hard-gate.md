# 10 — Scoring hard gate

**What to build:** Make Minds availability a hard gate on the scoring stage (ADR-0002). The pipeline currently degrades: unconfigured Minds or per-clip MindsError leaves clips unscored and the job still COMPLETES. Change to fail-closed: (a) before scoring, if `MINDS_BUILDER_API_KEY`/`MINDS_AGENT_ID` are missing, the job fails fast at the scoring stage with a clear error message; (b) any MindsError during `_score_clips` fails the job (existing rollback + FAILED + error_message machinery). No clip is ever persisted unscored.

**Blocked by:** none (extends shipped tickets 04/05)

**Status:** ready-for-agent

- [ ] Pre-flight check in `pipeline._score_clips` (or before it) raising a clear error when Minds is unconfigured
- [ ] Per-clip MindsError propagates → job FAILED with message, `db.rollback()` path already exists
- [ ] Remove the `continue`/unscored toleration in `pipeline.py` for scoring (memory-context fetch failure may still degrade — only verdict calls are gated)
- [ ] Tests: unconfigured Minds → job FAILED with message; per-clip MindsError → job FAILED; happy path unchanged; memory-fetch-only failure still allows scoring with `memory_context=None`