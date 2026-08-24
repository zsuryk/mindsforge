# 06 — Fix double trend injection in adaptations

**What to build:** Adaptation generation no longer injects trend data twice. The `build_chat_context()` function already includes system notifications (which contain trend research results), so the separate `build_trend_block(fetch_memory(...))` call in `_chat_context()` duplicates trend data in the prompt. The adaptations flow reads trends from the chat thread instead of SQLite.

**Blocked by:** None — can start immediately.

**Status:** completed

- [ ] Remove the `minds.fetch_memory()` call and `trends.build_trend_block()` call from `_chat_context()` in `adaptations.py`
- [ ] `_chat_context()` returns only `minds.build_chat_context()` — trend data is already in the conversation context as `[System]:` lines
- [ ] Update `_chat_context()` docstring to reflect that trends come from the chat thread, not SQLite
- [ ] Update tests in `test_adaptations.py` to verify no `fetch_memory` is called for trend injection
- [ ] Verify no other callers depend on the removed trend block path
