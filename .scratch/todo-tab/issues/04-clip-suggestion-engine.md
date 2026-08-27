# 04 — Clip suggestion engine

**What to build:** After clips are scored, analyse their stats and generate `clip_suggestion` TodoItems with actionable recommendations. This makes the Mind proactively help creators improve their content.

**Blocked by:** 01 (needs `TodoService` and the `TodoItem` model)

**Status:** done

- [ ] After scoring, check virality score and generate suggestions: score ≥80 → suggest A/B testing thumbnails; score ≤30 → suggest reviewing hooks or re-cutting
- [ ] When multiple clips come from the same job, suggest cross-platform adaptation
- [ ] Each suggestion TodoItem has `action_url` linking to the relevant clip and `action_label` like "View clip" or "Launch A/B test"
- [ ] Suggestions are not created for mid-range virality scores (31-79) to avoid noise
- [ ] Tests verify: high-virality clip produces thumbnail A/B suggestion, low-virality clip produces re-cut suggestion, multi-clip job produces adaptation suggestion, mid-range produces nothing
