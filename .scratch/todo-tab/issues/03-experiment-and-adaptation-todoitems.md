# 03 — Experiment + adaptation TodoItems

**What to build:** When an experiment concludes (or fails) and when an adaptation is generated, create an `experiment_result` TodoItem for the user-facing feed. The `notify_mind()` call is **retained** for these callers so the Mind still learns from the chat thread — the TodoItem is an additional output, not a replacement.

**Blocked by:** 01 (needs `TodoService` and the `TodoItem` model)

**Status:** resolved

- [x] `ab_testing._conclude_experiment` creates an `experiment_result` TodoItem with title summarising the winner and body containing the learned insight; `action_url` links to the experiment
- [x] `ab_testing._fail_experiment` creates an `experiment_result` TodoItem with the error message; `action_url` links to the experiment
- [x] `adaptations.generate_adaptation` (on READY) creates an `experiment_result` TodoItem with a brief feature summary; `action_url` links to the clip
- [x] `notify_mind()` calls are **kept** in all three callers — the Mind continues to learn from chat
- [x] Tests verify: each caller creates a TodoItem with correct type, title, and action_url; `notify_mind()` is still called
