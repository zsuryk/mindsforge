# 05 — Minds scoring and clip studio

**What to build:** Clips get smart. Each extracted clip's transcript is sent to the Mind, which scores it against stored historical insights and returns a structured verdict: virality score (0–100), suggested titles, and platform-specific hooks. These persist on the clip. In the UI, a clip studio page opens for any clip: it plays the video, shows a virality gauge, tabbed platform hooks (YouTube Shorts, TikTok, X), and a "Launch A/B Test" button (wired to a modal, launch itself lands in ticket 07).

**Blocked by:** 04 — Clip extraction

**Status:** done

- [x] Minds service module encapsulates the Builder API client (auth header, memory read/write helper) per the protocol in the spec
- [x] `generate_clip_metadata` prompts the Mind and returns the structured JSON (score, titles, hooks); parsing failures degrade gracefully
- [x] Scoring runs as part of the processing pipeline after extraction, persisting `virality_score` and `suggested_hooks`
- [x] Clip studio page: video player, virality gauge, hook tabs, Launch A/B Test button opening a variant-configuration modal
- [x] Studio renders a real scored clip with distinct per-platform hooks

## Comments

- `suggested_hooks` stores the full structured verdict (`suggested_titles` + per-platform `platform_hooks`) as a JSON dict.
- Scoring is best-effort: missing `MINDS_BUILDER_API_KEY`/`MINDS_AGENT_ID`, HTTP/network errors, or unparseable verdicts leave `virality_score`/`suggested_hooks` null and the job still completes.
- Note: `backend/.env` currently has empty Minds credentials, so live scoring degrades gracefully until keys are added.