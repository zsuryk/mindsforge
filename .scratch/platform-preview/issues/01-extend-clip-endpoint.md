# 01 — Extend clip endpoint with adaptation summaries

**What to build:** The `GET /clips/{id}` endpoint returns a `latest_adaptations` field: a list of `{platform, surface, status, features, assets}` summaries for each adaptation that exists for this clip. The field is `null` when no adaptations exist. The frontend can fetch everything in one request instead of calling the clip endpoint and adaptations endpoint separately.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Add `AdaptationSummary` schema to `backend/app/schemas/clip.py` with fields: `platform`, `surface`, `status`, `features` (JSON-serialisable dict), `assets` (JSON-serialisable dict or null)
- [x] Extend `ClipOut` schema with `latest_adaptations: list[AdaptationSummary] | None = None`
- [x] Update `_to_out()` in `backend/app/api/clips.py` to join `ClipAdaptation` rows for the clip and populate `latest_adaptations`
- [x] Return `latest_adaptations` as an empty list when no adaptations exist (not null — keeps frontend simpler)
- [x] Add backend test: `GET /clips/{id}` returns `latest_adaptations` with correct features/assets when adaptations exist
- [x] Add backend test: `GET /clips/{id}` returns empty `latest_adaptations` when no adaptations exist
