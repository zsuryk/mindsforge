# 06 — Memory inspector

**What to build:** A window into the Mind. A memory page fetches the agent's persistent memory context (`agent_id` + memory tree) from the Minds Builder API and renders it two ways: a grid of insight cards highlighting learned rules, and an interactive syntax-highlighted JSON tree of the raw context. A refresh button re-fetches. A manual update control posts a key/value into memory and reflects the result. This page is the showcase feature.

**Blocked by:** 05 — Minds scoring and clip studio

**Status:** done

- [x] Memory read endpoint returns agent id + memory tree; failures (missing key, API down) return a clear error
- [x] Memory update endpoint posts an insight key/value and returns success
- [x] Memory page: header with brain icon + agent tag, refresh button, insight cards grid
- [x] Interactive JSON tree viewer renders the raw memory context with syntax highlighting
- [x] Manual update from the UI is visible on next refresh

## Comments

- `GET /agent/memory` → `{agent_id, memory}`; `POST /agent/memory/update` → `{success}` (new `app/api/memory.py`).
- Error mapping: missing `MINDS_*` config → 503, other Builder API failures → 502, both with a clear detail message; the frontend surfaces them in the page.
- Insight cards are derived from the memory tree: `brand_voice`, per-platform `historical_insights` items, and `ab_test_history` records carrying a `learned_insight` (`lib/insights.ts`).
- The JSON tree (`components/json-tree.tsx`) is collapsible per node with syntax-colored tokens; the root starts expanded.
- The write control parses the value input as JSON when valid, else treats it as text; after a successful write the page re-fetches so the new key appears in the tree immediately.
