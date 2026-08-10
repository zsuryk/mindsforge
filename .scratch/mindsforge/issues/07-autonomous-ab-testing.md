# 07 — Autonomous A/B testing

**What to build:** The self-improving loop. A user launches a multi-variant A/B test on a clip for a platform (variants configured from the ticket 05 modal, each with title + thumbnail). The experiment persists as ACTIVE. A background worker loop (every 60s) refreshes each active experiment's variant views/CTR (simulated when no live platform API), and when the cumulative view threshold is reached it concludes the experiment: picks the highest-CTR variant, records the winner, generates a natural-language learned insight, and writes it into the Mind's persistent memory. The experiments page lists active tests, shows a Recharts CTR comparison of variants, and displays a highlighted banner when an experiment concludes with its winning variant and the insight written to memory.

**Blocked by:** 04 — Clip extraction, 05 — Minds scoring and clip studio

**Status:** ready-for-agent

- [ ] Experiment model + start endpoint persist a multi-variant experiment with thumbnail paths; launch modal from ticket 05 works end-to-end
- [ ] Active experiments endpoint returns active + recently concluded experiments
- [ ] Background worker updates simulated views/CTR on a configurable interval and concludes experiments past the view threshold, selecting highest CTR
- [ ] Conclusion writes winner id, `concluded_at`, flag status CONCLUDED, and persists a generated insight via the Minds memory update
- [ ] Experiments page: variant cards with live view counts, CTR comparison chart, concluded insight banner
- [ ] A launched experiment runs to conclusion unattended and its insight appears in memory