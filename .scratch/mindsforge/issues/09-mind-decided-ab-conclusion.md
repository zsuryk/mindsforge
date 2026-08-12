# 09 — Mind-decided A/B conclusion

**What to build:** Replace the Python `highest-CTR` conclusion of ticket 07 with a Mind decision. When an ACTIVE experiment crosses the view threshold, the worker asks the Mind to pick the winner: prompt with the clip's platform, its variants (id, title, thumbnail, views, clicks, CTR), the clip transcript, and the creator's memory context; the Mind returns structured JSON `{winning_variant_id, reasoning}`. The `reasoning` becomes `learned_insight`, persisted to Minds memory via `ab_test_history` exactly as today. If the Mind call fails (unconfigured, network, or unparseable verdict), the experiment transitions to FAILED with `error_message` stored — no fallback to max-CTR (ADR-0002).

**Blocked by:** none (extends shipped ticket 07)

**Status:** ready-for-agent

- [ ] `minds.decide_experiment_winner(platform, variants, transcript, memory_context)` — structured prompt + `_parse_*` verdict handling, mirroring `generate_clip_metadata` conventions (MindsError on any failure)
- [ ] Winner id validated against the experiment's variants; reasoning non-empty
- [ ] `ab_testing._conclude_experiment` uses the Mind verdict; Mind failure → status FAILED + `error_message` (add column) instead of concluding
- [ ] `ab_experiments` migration: `variant_kind` enum (TITLE default for existing rows) + `error_message`
- [ ] Tests: happy path verdict, invalid-winner id rejected, all Minds failure modes fail the experiment with error message, `ab_test_history` still appended, ticket-07 tests updated (they assert Python-selected winners)
- [ ] `generate_learned_insight` (Python) deleted; reasoning comes from the Mind