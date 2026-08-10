# 06 — Memory inspector

**What to build:** A window into the Mind. A memory page fetches the agent's persistent memory context (`agent_id` + memory tree) from the Minds Builder API and renders it two ways: a grid of insight cards highlighting learned rules, and an interactive syntax-highlighted JSON tree of the raw context. A refresh button re-fetches. A manual update control posts a key/value into memory and reflects the result. This page is the showcase feature.

**Blocked by:** 05 — Minds scoring and clip studio

**Status:** ready-for-agent

- [ ] Memory read endpoint returns agent id + memory tree; failures (missing key, API down) return a clear error
- [ ] Memory update endpoint posts an insight key/value and returns success
- [ ] Memory page: header with brain icon + agent tag, refresh button, insight cards grid
- [ ] Interactive JSON tree viewer renders the raw memory context with syntax highlighting
- [ ] Manual update from the UI is visible on next refresh