# 22 — Real-data feedback for experiments

**What to build:** Let a creator feed real view/click numbers into an ACTIVE
experiment. Variant metrics become editable; editing flips the experiment to
`data_source=MANUAL`, the simulation worker stops touching it, and it still
concludes at the view threshold with the Mind's verdict — so a clip published
via the checklist can be A/B-tested on reality, not simulation.

**Blocked by:** none

**Status:** ready-for-agent

## Problem Statement

The A/B experiment is the product's autonomy centrepiece, but its traffic is
simulated — the one thing a sharp judge can see through on "Viability &
Scalability". There is no path for real post-publish data to enter an
experiment, and nothing marks an experiment as running on real numbers.

## Solution

- Migration `0006_add_ab_data_source`: `ab_experiments.data_source` enum
  (`SIMULATED`, `MANUAL`), server default `SIMULATED`, not null.
- `PATCH /ab-tests/{experiment_id}/variants/{variant_id}` with body
  `{views: int, clicks: int}`:
  - 404 for an unknown experiment or variant id; 422 for a non-ACTIVE
    experiment (no edits after conclusion), negative numbers, or
    `clicks > views`;
  - updates the variant's `views`/`clicks`, recomputes `ctr` as
    `clicks / views * 100` (rounded to 2dp);
  - sets `data_source = "MANUAL"` on the experiment;
  - returns the updated experiment (same shape as `GET /ab-tests/active`
    rows).
- `ab_testing.refresh_active_experiments` skips experiments with
  `data_source == MANUAL` entirely (no simulated sweeps on top of real
  numbers); they still conclude normally when their cumulative views cross
  the threshold (Mind verdict + insight unchanged).
- `GET /ab-tests/active` returns `data_source` per experiment.
- Frontend (`frontend/app/ab-experiments/`):
  - each ACTIVE experiment card gains a "simulated" / "manual" badge;
  - per-variant inline edit for ACTIVE experiments: views/clicks inputs +
    save button calling the PATCH; after save, the card shows the updated
    numbers and the manual badge.

## User Stories

1. As a creator, I want to enter the real view and click numbers of my
   published clip into an active test, so the winner is decided on reality.
2. As a creator, I want the UI to clearly mark which experiments run on
   simulation and which on real data, so I trust what the conclusion means.
3. As an operator, I want manual experiments to never accumulate simulated
   traffic, so real numbers stay real.

## Implementation Decisions

- `clicks > views` is rejected (422): an impossible ratio is a data-entry
  error, and the fail-closed convention (ADR-0002) prefers a loud error over
  silent correction.
- Only ACTIVE experiments are editable — the worker concludes at the
  threshold and a concluded verdict is the Mind's, not the creator's.
- The Mind's verdict prompt is unchanged: it already receives views/clicks/
  CTR per variant, and the learned insight flows into `ab_test_history`
  exactly as before — only the data source differs.

## Testing Decisions

- `backend/tests/test_ab_testing.py`:
  - PATCH updates metrics + recomputes CTR + flips `data_source`;
  - 404s (unknown experiment/variant), 422s (non-ACTIVE, negative,
    clicks > views);
  - the sweep skips MANUAL experiments (no views accumulate) but concludes
    one whose manual totals already exceed the threshold;
  - `GET /ab-tests/active` exposes `data_source`.
- `backend/tests/test_migrations.py`: the migration adds the column with the
  default, downgrade drops it.
- `frontend/app/ab-experiments.test.tsx`: badge renders per source; editing
  an ACTIVE variant calls the PATCH and updates the card; edits are absent on
  CONCLUDED/FAILED experiments.

## Out of Scope

- CSV/bulk import of metrics (manual entry covers the demo; import is a
  production nicety).
- Seeding simulated experiments from public view counts (yt-dlp scrape) —
  stretch idea, not required.
- A "revert to simulated" action (once manual, always manual).
- Publishing integrations (ADR-0001 stands).

## Further Notes

Commit on `main` as a single conventional `feat(ab-tests): …` commit,
including the migration.