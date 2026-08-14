# 14 — Review fixes for tickets 09-13

**What to build:** Fix the defects surfaced by the code review of tickets 09-13
(Mind-decided experiment conclusion, scoring hard gate, adaptation domain,
adaptation assets, adaptation studio UI). Each fix below restores the behaviour
its originating ticket already promised — no new features.

**Blocked by:** none

**Status:** ready-for-agent

## Problem Statement

The review of tickets 09-13 found real defects: the Mind concludes a
thumbnail-kind Experiment without seeing thumbnails, a failed Experiment is
unreadable because FAILED rows are filtered from every API response, an unknown
exception during conclusion aborts the whole worker sweep instead of failing
one Experiment, a clip-less job COMPLETES while Minds is unconfigured, the
feature-manifest validator accepts impossible platform-surface pairings and
manifests missing required features, two concurrent adaptation requests can
500 on the unique constraint, memory history records a success before the row
is READY, chapter timestamps in `chapters.txt` differ from what the creator
copies from the manifest panels, per-brief overlay styles are ignored, excess
overlay specs are silently dropped, a test assertion is a tautology, a
long-form video Experiment is labelled "YouTube Shorts", tags are not chips,
"Test & Compare" appears on non-youtube surfaces, and the "Regenerate" button
promises work the backend never performs.

## Solution

Make every implemented promise true:

- The Mind's winner prompt lists each variant's thumbnail reference alongside
  its metrics; prompt copy uses the glossary terms (Experiment, Learned
  insight).
- Any failure while concluding an Experiment fails that Experiment closed,
  never the worker sweep; FAILED Experiments (with their error message) are
  returned by the API within the recency window and shown on the experiments
  page.
- Scoring is fail-closed for every job that reaches the scoring stage,
  including clip-less ones; the unconfigured-Minds test asserts no clip is
  ever persisted unscored.
- Feature-manifest validation is a single required-features table keyed by
  platform-surface; impossible pairings are rejected and LONG_FORM manifests
  must carry a shorts-link suggestion.
- Concurrent adaptation generation requests converge on the cached row instead
  of 500ing; the `adaptation_history` memory write-back happens only after the
  row is READY.
- `chapters.txt` carries the Mind's timestamps verbatim; thumbnail overlays
  honour the brief's style choice; excess overlay specs render as a clear
  error → FAILED instead of silently vanishing.
- Experiments gain a long-form platform value so YouTube Video tests are
  labelled correctly; tags render as chips; "Test & Compare" is youtube-only;
  no button promises regeneration the backend doesn't perform.

## User Stories

1. As a creator, I want the Mind to see each experiment variant's thumbnail
   when deciding the winner of a thumbnail test, so its verdict is grounded in
   what viewers saw.
2. As a creator, I want to know why an experiment failed, so I can fix the
   underlying issue instead of discovering it by accident.
3. As an operator, I want one broken experiment to never take down the
   conclusion sweep for every other experiment, so a single bad row cannot
   silence the whole pipeline.
4. As a creator, I want a silent video I uploaded to fail visibly when Minds is
   unconfigured, so I am not fooled into thinking scoring ran.
5. As a creator, I want the downloads on an adaptation to match the manifest
   panels I copy from, so what I publish is what the Mind authored.
6. As a creator, I want thumbnail overlays to look like the Mind's brief (bold
   vs italic, placement), so the rendered asset matches the plan.
7. As a developer, I want impossible platform-surface manifests rejected at
   validation time, so bad feature shapes never reach the renderer.
8. As a developer, I want two people clicking "Generate" at once to both end
   up with the same adaptation row, so nothing 500s on a race.
9. As a creator, I want an A/B test on my long-form video labelled "YouTube
   Video", not "YouTube Shorts", so the dashboard tells the truth.
10. As a creator, I want tags displayed as chips, so I can copy them as a set.
11. As a creator, I want "Test & Compare" offered only where YouTube supports
    it, so I am not offered a thumbnail A/B on TikTok or X.
12. As a creator, I want buttons to do what they say: "Generate" returns the
    cached adaptation, and a failed adaptation offers a working "Retry".
13. As a developer, I want the confidence that an apparently passing assertion
    actually asserts something, so the suite catches regressions.

## Implementation Decisions

### Experiment conclusion (ticket 09 area)

- `_build_winner_prompt` variant lines gain the variant's thumbnail reference
  (the stored `thumbnail_path`; experiments always carry one) so the prompt
  matches the ticket-09 contract: id, title, thumbnail, views, clicks, CTR.
  The Minds Builder API is text-only: the reference is the file path — image
  attachments are out of scope.
- Prompt copy drops banned vocabulary: "A/B testing analyst" → experiment
  analyst; "lesson" → learned insight.
- The conclusion sweep catches **any** exception from `_conclude_experiment`
  (not just `MindsError`) and fails that Experiment closed with the message;
  the sweep continues with the remaining experiments.
- `GET /ab-tests/active` includes FAILED Experiments within the recency window
  (their rows today are otherwise unfetchable); the experiments page shows a
  FAILED badge plus the stored `error_message` (Retry on the experiments page
  is out of scope — failures come from the simulation worker, there is no
  re-run trigger).

### Scoring gate (ticket 10 area)

- The Minds-configuration check moves above the clips query in the scoring
  stage and raises the existing `MindsConfigError` (not a bare `RuntimeError`);
  a clip-less job with Minds unconfigured now FAILS with the clear message.
- The unconfigured-Minds test asserts `clips == []` after the failure (the
  vacuous `all(... is None)` assertion is replaced), matching the per-clip
  failure test's rollback assertion.

### Adaptation domain (ticket 11 area)

- Feature validation becomes one required-features table keyed by
  (platform, surface) consumed by the model validator: impossible pairings
  (tiktok/LONG_FORM, x/SHORTS, youtube/POST, …) are rejected, and LONG_FORM
  requires `shorts_link`. The table replaces the current platform-ignoring
  branch cascade.
- The lazy-generation POST handles the concurrent-insert race: on unique
  constraint violation, roll back, re-select the winning row, and return it as
  the cached 200 the loser would have gotten.
- `_persist_adaptation_history` runs **after** the row is committed READY, so
  memory never records a success for a row still marked GENERATING. The
  write-back stays best-effort (existing convention, ticket-07/11 precedent).

### Assets (ticket 12 area)

- `chapters.txt` writes the Mind's chapter timestamps verbatim — the
  nearest-segment-start snap is removed so downloads match the manifest panels.
- Thumbnail compositing honours the brief's style choice: `overlay_spec` items
  carry `style` (bold/italic) and `caption_style` is applied to the caption
  placement, instead of every thumbnail getting identical bold text.
- POST overlay specs are paired with clip-window frames by index; when the
  spec count exceeds the segment count the render fails with a clear error →
  adaptation FAILED (no silent drop).
- The tautological SRT assertion gains `in content`.

### Studio UI (ticket 13 area)

- The experiment `Platform` vocabulary gains `"youtube"` (long-form). The
  studio launches SHORTS tests with `youtube_shorts` and LONG_FORM tests with
  `youtube`; the experiments page labels `youtube` as "YouTube Video".
- Tags render as chips in the manifest panel.
- "Run Test & Compare" renders only for youtube surfaces
  (SHORTS and LONG_FORM).
- The button label never claims regeneration: READY rows keep cache semantics
  and the button reads "Generate"; FAILED rows read "Retry" (re-POST restarts
  the attempt, which the backend already supports).
- Enum comparisons use the `AbExperimentVariantKind` member, not `.value` vs
  string literals; the frontend reuses the exported kind type instead of
  re-declaring `"TITLE" | "THUMBNAIL"` unions.

### Small cleanups (from the same review)

- Drop the unused `db` parameter of `render_adaptation_assets`.
- Comment the `/media` route remount in the lifespan.
- Rename the `test_pending_rerquest` typo.

## Testing Decisions

Good tests here assert external behaviour (API response shape, persisted rows,
file contents, rendered copy) — not implementation details like prompt string
construction or call order. The existing seams are reused, one per area:

- **Backend pytest**: `test_ab_testing.py` (winner prompt additions, exception
  isolation, FAILED rows visible via the API), `test_pipeline.py` +
  `test_clips.py` (gate placement, `clips == []` under unconfigured Minds),
  `test_adaptations.py` (validation table, race re-select, memory write-back
  ordering), `test_adaptation_assets.py` (verbatim chapters, styled overlays,
  excess-spec failure, fixed SRT assertion). Prior art: the fail-closed and
  rollback tests already in those files.
- **Frontend vitest**: `adaptation-studio.test.tsx` (chips, youtube-only Test &
  Compare, honest labels), `ab-experiments.test.tsx` (FAILED badge + error
  message, "YouTube Video" label). Prior art: the existing component tests.

## Out of Scope

- Real regeneration (forcing a fresh attempt for a READY adaptation) — the
  button is relabelled, the cache semantics stay.
- Sending actual images to the Minds Builder API.
- Memory-fetch degradation in scoring (still allowed to degrade to
  `memory_context=None`, per ticket 10).
- A re-run trigger for failed experiments; platform-surface matrix
  consolidation (validation table only, from ticket 14 itself); deep style
  engine work for overlays beyond the basic bold/italic/caption-zone choices.

## Further Notes

Ticket files 09-13 are already marked done; this ticket is the review follow-up
and does not reopen them. Commit on `main` as a single conventional
(`fix(…):`) commit or split per area if the diff gets large.