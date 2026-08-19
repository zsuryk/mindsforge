# 20 — Mind at Work activity feed

**What to build:** Make the Mind's background work visible. A `mind_activity`
table logged by every Mind-touching service (scoring, experiment sweeps,
conclusions, adaptations, trend research, chat) and surfaced as a live
"Mind at Work" panel on the dashboard, polling every 5s. The silent A/B
worker becomes a visible 24/7 heartbeat.

**Blocked by:** none

**Status:** ready-for-agent

## Problem Statement

The Mind scores clips, sweeps experiments every 60s, concludes winners,
generates adaptations, and writes memory — all invisibly. The hackathon's
"Background Execution" strength is unprovable on screen: nothing shows the
Mind working. The product needs a visible, live record of what the Mind is
doing right now.

## Solution

- Migration `0007_create_mind_activity`: table `mind_activity`
  (`id` UUID pk, `event_type` String(64), `label` String(255),
  `detail` JSON nullable, `ref_id` String(64) nullable, `created_at`).
- New `app/services/activity.py`:
  - `log(event_type, label, detail=None, ref_id=None)` — insert a row; trim
    the table to the newest 500 rows on insert (bounded growth).
- Call sites (one row per event, never per variant):
  - `pipeline` scoring stage — "clip-scored": "Scored clip '<title>' —
    virality 82/100" (per clip, `ref_id=clip.id`).
  - `ab_testing.refresh_active_experiments` sweep — "experiment-sweep":
    "Simulated sweep: +N views across M variants" (one row per sweep, even
    with zero experiments: the worker is alive and proving it).
  - `ab_testing._conclude_experiment` / `_fail_experiment` —
    "experiment-concluded" / "experiment-failed".
  - `adaptations.generate_adaptation` READY / FAILED — "adaptation-ready" /
    "adaptation-failed".
  - `trends` research — "trend-researched": "'<query>' — N results".
  - chat rule save (ticket 17) — "rule-saved": "'<text>'".
  - chat notification posted (ticket 18) — "mind-notified".
- `GET /dashboard/activity?limit=20` → `[{id, event_type, label, detail,
  created_at}]` (newest first). Lives on the existing dashboard router.
- Dashboard: "Mind at Work" panel above/beside the metric cards —
  icon per event type, label, relative time ("12s ago"), 5s polling, empty
  state "The Mind is idle — submit a job to see it work." Newest event
  highlighted.

## User Stories

1. As a creator, I want to watch my Mind working (scoring, experimenting,
   adapting) from the dashboard, so the "24/7 background" claim is visible.
2. As a judge/demo watcher, I want to see the experiment worker pulse every
   minute, so the autonomy story proves itself live.
3. As an operator, I want the activity log bounded, so a long-running demo
   never grows the database without limit.

## Implementation Decisions

- `event_type` is a free-form string (icon map lives in the frontend), not an
  enum — adding event types later must not require a migration.
- The sweep logs a single row even when no experiment is ACTIVE: an empty
  heartbeat is still proof the worker runs.
- `activity.log` must never raise into its callers (wrap in try/except, log
  the failure) — logging is observability, not a gate.

## Testing Decisions

- `backend/tests/test_activity.py`: insert + trim cap (500), newest-first
  ordering, API shape, unknown dashboard state stays 200 with empty list.
- `backend/tests/test_dashboard.py` extended: the activity endpoint returns
  rows logged by a simulated sweep and a scoring pass.
- `backend/tests/test_ab_testing.py`: a sweep logs exactly one
  "experiment-sweep" row; conclusion logs "experiment-concluded".
- `frontend/app/dashboard.test.tsx` extended: the panel renders events with
  icons and relative times, polls, and shows the empty state.

## Out of Scope

- A dedicated full-page activity log (the dashboard panel suffices for the
  demo).
- Persisting activity across restarts beyond the SQLite row lifetime (rows
  survive restarts by default — the 500-row cap is the only trimming).
- Streaming/SSE updates (5s polling matches existing dashboard patterns).

## Further Notes

Commit on `main` as a single conventional `feat(dashboard): …` commit,
including the migration.