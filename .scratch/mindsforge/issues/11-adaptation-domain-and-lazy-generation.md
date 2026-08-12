# 11 — Adaptation domain & lazy generation

**What to build:** The adaptation domain. New concepts (glossary: `CONTEXT.md`): Platform (youtube, tiktok, x) + Surface (SHORTS, LONG_FORM, POST — youtube has shorts+long_form, tiktok=x=post-style single surface). New model `clip_adaptations` (clip_id FK, platform, surface, status PENDING/GENERATING/READY/FAILED, features JSON, assets JSON (paths, populated by ticket 12), error_message, created_at, updated_at) + Alembic migration. Lazy generation: `GET /clips/{id}/adaptations`, `POST /clips/{id}/adaptations/{platform}/{surface}` → 202, starts a background task (FastAPI BackgroundTasks, mirroring the job pipeline pattern); a READY or PENDING row is returned as-is on re-request (cache). Generation = `minds.generate_adaptation_features(clip, platform, surface, segments, memory_context)` — the Mind authors the full feature manifest per surface:

- **youtube/LONG_FORM:** chapters (with timestamps, later matched to segment boundaries), video tags, community poll (question + options), quiz (Q&A pairs), Test & Compare thumbnail briefs (3 × {frame_timestamp hint, overlay_text}), shorts-link suggestion (which Short of this creator to link)
- **youtube/SHORTS:** Test & Compare thumbnail briefs (3 × {frame_timestamp hint, overlay_text}), reuse of platform hooks
- **tiktok/POST:** native text-overlay styles (per-segment overlay text + placement/style spec), auto-caption styling note, interactive sticker suggestions (emoji/poll sticker + placement), pinned comment text
- **x/POST:** caption + hashtags (thin — X has no rich features)

Prompt includes creator memory context; on success append an `adaptation_history` record to Minds memory (per-surface record of what was produced) — read `adaptation_history` back into future adaptation prompts (compounding loop). On Minds failure → adaptation FAILED + error_message (fail-closed per ADR-0002, consistent with ticket 10).

**Blocked by:** 10 — Scoring hard gate

**Status:** ready-for-agent

- [ ] `Platform`/`Surface` vocabulary in schemas (platform strings stay `youtube|tiktok|x`; `youtube` gets two surfaces)
- [ ] `clip_adaptations` model + Alembic migration + API: list, generate (202 + background task), get-by-id
- [ ] `minds.generate_adaptation_features` prompt per surface with structured-verdict parsing + validation, MindsError conventions
- [ ] Lazy generation service with status transitions, error handling, and READY/PENDING cache semantics
- [ ] `adaptation_history` write-back on success + included in memory context on subsequent generations
- [ ] Tests: lifecycle (PENDING→READY, FAILED on Minds error, no duplicate generation while cached), per-surface manifest shapes, memory write-back content