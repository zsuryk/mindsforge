# 05 — X preview

**What to build:** `XPreview` renders a tweet-shaped mockup with platform label, showing caption text, hashtag pills, and a character count indicator. Fallback: "Generate adaptation to preview" prompt when no adaptation exists.

**Blocked by:** 02 — Preview canvas scaffold + YouTube Shorts preview

**Status:** done

- [x] Create `XPreview` component in `frontend/components/previews/`
- [x] Accept typed props: `caption: string`, `hashtags: string[]`
- [x] Render tweet-shaped card with X-colored border and "X" label
- [x] Render caption text inside the card
- [x] Render hashtags as pill-shaped badges below the caption
- [x] Render character count indicator (caption length / 280)
- [x] Horizontal frame with letterboxing to fit sidebar width
- [x] Fallback: empty frame with "Generate adaptation to preview" text when no adaptation features exist
- [x] Copy icons on caption and individual hashtags
- [x] Component tests: renders caption/hashtags/character count when features exist, renders fallback when empty
