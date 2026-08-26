# 05 — X preview

**What to build:** `XPreview` renders a tweet-shaped mockup with platform label, showing caption text, hashtag pills, and a character count indicator. Fallback: "Generate adaptation to preview" prompt when no adaptation exists.

**Blocked by:** 02 — Preview canvas scaffold + YouTube Shorts preview

**Status:** ready-for-agent

- [ ] Create `XPreview` component in `frontend/components/previews/`
- [ ] Accept typed props: `caption: string`, `hashtags: string[]`
- [ ] Render tweet-shaped card with X-colored border and "X" label
- [ ] Render caption text inside the card
- [ ] Render hashtags as pill-shaped badges below the caption
- [ ] Render character count indicator (caption length / 280)
- [ ] Horizontal frame with letterboxing to fit sidebar width
- [ ] Fallback: empty frame with "Generate adaptation to preview" text when no adaptation features exist
- [ ] Copy icons on caption and individual hashtags
- [ ] Component tests: renders caption/hashtags/character count when features exist, renders fallback when empty
