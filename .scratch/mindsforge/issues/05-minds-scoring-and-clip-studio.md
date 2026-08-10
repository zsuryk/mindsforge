# 05 — Minds scoring and clip studio

**What to build:** Clips get smart. Each extracted clip's transcript is sent to the Mind, which scores it against stored historical insights and returns a structured verdict: virality score (0–100), suggested titles, and platform-specific hooks. These persist on the clip. In the UI, a clip studio page opens for any clip: it plays the video, shows a virality gauge, tabbed platform hooks (YouTube Shorts, TikTok, X), and a "Launch A/B Test" button (wired to a modal, launch itself lands in ticket 07).

**Blocked by:** 04 — Clip extraction

**Status:** ready-for-agent

- [ ] Minds service module encapsulates the Builder API client (auth header, memory read/write helper) per the protocol in the spec
- [ ] `generate_clip_metadata` prompts the Mind and returns the structured JSON (score, titles, hooks); parsing failures degrade gracefully
- [ ] Scoring runs as part of the processing pipeline after extraction, persisting `virality_score` and `suggested_hooks`
- [ ] Clip studio page: video player, virality gauge, hook tabs, Launch A/B Test button opening a variant-configuration modal
- [ ] Studio renders a real scored clip with distinct per-platform hooks