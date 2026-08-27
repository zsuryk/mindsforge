# 02 — Weekly digest generation

**What to build:** Enrich the weekly trends loop to produce a `weekly_digest` TodoItem containing top trending topics, clip performance summary, and actionable suggestions. This replaces the system message that was posted to chat for weekly digests.

**Blocked by:** 01 (needs `TodoService` and the `TodoItem` model)

**Status:** resolved

- [x] The weekly trends loop creates a `weekly_digest` TodoItem after completing its research
- [x] Digest body includes: top 3 trending topics from the week's research, clip performance summary (total clips, average virality, top performer), 1-2 actionable suggestions based on stats
- [x] The existing `notify_mind()` call in the weekly trends loop is replaced with `create_todo_item()` — no system message is posted to chat for this event
- [x] The `action_url` and `action_label` fields are populated when applicable (e.g., link to a top-performing clip)
- [x] Tests verify: digest TodoItem is created with correct type and structured body, no chat message is posted
