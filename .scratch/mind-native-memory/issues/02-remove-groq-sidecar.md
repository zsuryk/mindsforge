# 02 — Remove Groq brand-rule extraction sidecar

**What to build:** The Groq dependency is eliminated. Brand-rule extraction is handled natively by the Mind in its conversation thread.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Delete `rules.py` entirely (extraction, persistence, `extract_and_persist_brand_rules`)
- [x] Remove `rules` import and call from `api/chat.py`
- [x] Remove `rules` field from `ChatSendOut` schema in `schemas/chat.py`
- [x] Remove `MEMORY_CONTEXT_KEYS` and `build_memory_context()` from `minds.py`
- [x] Delete or rewrite `test_rules.py` tests
- [x] Verify no remaining references to `rules.py` or Groq extraction in the codebase
