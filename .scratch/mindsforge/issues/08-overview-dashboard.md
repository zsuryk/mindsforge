# 08 — Overview dashboard

**What to build:** The landing page that ties the product together. `/` shows the "MindsForge Studio" header with a system status badge and a rapid URL-processing input bar that submits a job and takes the user to it. Four metric cards aggregate live data: total clips generated, active A/B experiments, average virality score, and total insights learned. A recent-jobs table lists the newest jobs with animated status badges linked to their details.

**Blocked by:** 04 — Clip extraction, 06 — Memory inspector, 07 — Autonomous A/B testing

**Status:** ready-for-agent

- [ ] Dashboard header + system status badge + URL input bar that kicks off a job
- [ ] Four metric cards read from live aggregates; counts stay correct as jobs/clips/experiments change
- [ ] Recent jobs table with animated status badges, linked to job detail
- [ ] Empty states render gracefully before any data exists
- [ ] End-to-end walkthrough works: submit URL → watch job → saw clips → launch A/B → numbers on the dashboard move