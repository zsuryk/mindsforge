# 23 — Platform preview canvas

**What to build:** Replace the "Platform hooks" card in the clip studio sidebar with a visual preview canvas that renders platform-native frames for each surface. The creator sees hooks, polls, quizzes, overlays, stickers, and thumbnails as they'd appear on the actual platform.

**Blocked by:** 13 — Adaptation studio UI

**Status:** ready-for-agent

## Implementation tickets

- 01 — Extend clip endpoint with adaptation summaries (no blockers)
- 02 — Preview canvas scaffold + YouTube Shorts preview (blocked by 01)
- 03 — YouTube Long-form preview (blocked by 02)
- 04 — TikTok preview (blocked by 02)
- 05 — X preview (blocked by 02)
- 06 — Adaptation studio cleanup + copy-in-preview (blocked by 03, 04, 05)

## Scope

### Backend
- Extend `GET /clips/{id}` to include `latest_adaptations` field (per-surface summaries with features, assets, status)

### Frontend — Preview components
- `YouTubeShortsPreview` — vertical frame, 3 thumbnail variants (1 large + 2 small), hook overlay text
- `YouTubeLongFormPreview` — horizontal frame, poll card, quiz card, chapters list, shorts link
- `TikTokPreview` — vertical 9:16 frame, overlay text at placements, sticker emoji, pinned comment bubble
- `XPreview` — tweet mockup, caption, hashtag pills, character count

### Frontend — Layout
- Sidebar fixed-width, preview scales to fit (pillarbox/letterbox)
- Tabs match adaptation studio (4 surfaces)
- Virality gauge stays above preview
- Copy icons on visual elements

### Frontend — Adaptation studio
- Remove visual feature CopyBlocks (hooks, polls, quizzes, overlays, stickers, chapters, thumbnails)
- Keep non-visual CopyBlocks (tags, hashtags, captions, shorts_link)

### Testing
- Component tests per preview surface
- Fallback rendering tests
- Copy-to-clipboard tests
- Layout stability tests
