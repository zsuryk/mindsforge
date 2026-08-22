# 01 — Inject conversation thread into generation prompts

**What to build:** Clip scoring, adaptation generation, and experiment conclusion are all grounded in the Mind's own conversation thread instead of SQLite. The Mind sees its full chat history when making every decision.

**Blocked by:** None — can start immediately.

**Status:** done (38183c1)

- [x] `build_chat_context()` in `minds.py` fetches chat history, renders role-annotated text block, caps at ~4000 chars, excludes init instruction
- [x] `CHAT_INIT_INSTRUCTION` updated to prime the Mind to explicitly reference its memory when scoring/adapting
- [x] `pipeline.py:_score_clips()` uses `build_chat_context()` instead of `fetch_memory()` + `build_memory_context()`
- [x] `adaptations.py:_memory_context()` uses `build_chat_context()` instead of SQLite fetch; keeps curated trend block (filtered from chat notifications)
- [x] `ab_testing.py:_conclude_experiment()` uses `build_chat_context()` instead of SQLite fetch
- [x] Rename `memory_context` parameter to `chat_context` in `generate_clip_metadata()`, `generate_adaptation_features()`, `decide_experiment_winner()`
- [x] Unit tests for `build_chat_context()` covering: normal history, empty history, character cap, init instruction filtering, role annotation
