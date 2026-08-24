# Suppress zero-activity sweep logs

The A/B worker loop calls `refresh_active_experiments()` on a timer. Every invocation previously logged an `experiment-sweep` activity row unconditionally — even when zero experiments existed or zero new views were simulated. These "+0 views across 0 variants" rows flooded the "Mind at Work" dashboard panel with noise, making it harder to spot meaningful activity.

We now only log the sweep row when at least one of: new views were accumulated (`new_views_total > 0`) or experiments were concluded. Zero-activity sweeps are still executed (the worker loop keeps running), but they no longer produce dashboard noise.

**Considered Options:**
- Always log, but mark zero-sweep rows as lower priority — adds complexity to the activity schema and UI filtering for no real benefit.
- Increase the sweep interval to reduce frequency — trades responsiveness for fewer rows, but the real problem is the noise itself, not the cadence.

**Consequences:**
- The "Mind at Work" panel shows only actionable events.
- The worker loop behaviour is unchanged — it still runs on schedule and simulates traffic.
- Existing activity rows with actual views or conclusions are unaffected.
- Tests updated to expect zero rows when nothing happened.
