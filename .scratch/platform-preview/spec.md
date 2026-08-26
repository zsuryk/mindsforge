# Platform Preview Canvas — Spec

## Problem Statement

The clip studio's "Platform hooks" card renders hooks as plain text strings in a numbered list. The backend generates rich, structured feature manifests — polls, quizzes, overlays, stickers, chapters, thumbnail briefs — but the frontend reduces them to copyable text blocks. The README promises platform-adapted content with native features (polls, quizzes, stickers, overlays), but the hook pane just shows strings like a menu. Creators cannot see what their content will look like on each platform before they publish.

## Solution

Replace the "Platform hooks" card in the clip studio sidebar with a **platform preview canvas** — a visual render of each platform-surface's features in platform-native frames. The creator sees hooks, polls, quizzes, overlays, stickers, and thumbnails as they'd appear on the actual platform, not as text lists. The preview enriches automatically as adaptations are generated: clip-level hooks show first, then the full feature manifest renders once the adaptation is READY.

## User Stories

1. As a creator, I want to see my YouTube Shorts hooks rendered as thumbnail previews with overlay text, so I can evaluate which hook looks best before publishing.
2. As a creator, I want to see my YouTube Long-form poll rendered as a visual card with radio buttons, so I can verify the poll reads well.
3. As a creator, I want to see my YouTube Long-form quiz rendered as a question-and-answer card, so I can check the quiz flow before attaching it.
4. As a creator, I want to see my YouTube Long-form chapters as a timestamped list, so I can verify chapter titles and timing.
5. As a creator, I want to see my TikTok overlays rendered at their placement positions in a vertical 9:16 frame, so I can check overlay positioning and readability.
6. As a creator, I want to see my TikTok stickers placed at their designated positions, so I can verify emoji placement before publishing.
7. As a creator, I want to see my TikTok pinned comment as a chat bubble below the video frame, so I can read it in context.
8. As a creator, I want to see my X post rendered as a tweet mockup with caption and hashtag pills, so I can verify the post reads well and hashtags are visible.
9. As a creator, I want to see a character count indicator on the X preview, so I know if my caption fits within the platform limit.
10. As a creator, I want the preview to show platform labels (YouTube Shorts, TikTok, X) so I can instantly identify which surface I'm viewing.
11. As a creator, I want the preview to use platform-colored frames (YouTube red, TikTok black/cyan, X black/blue) so the surface is visually distinct.
12. As a creator, I want to copy a hook, poll question, or caption directly from the preview with a single click, so I don't have to switch to the adaptation studio.
13. As a creator, I want the preview tabs to match the adaptation studio tabs (YouTube Shorts, YouTube Video, TikTok, X), so I have one consistent mental model.
14. As a creator, I want to see the virality gauge above the preview, so I have context on clip quality while reviewing hooks.
15. As a creator, I want the sidebar to maintain a fixed width when switching preview tabs, so the layout doesn't shift.
16. As a creator, I want vertical previews (Shorts, TikTok) to scale within the sidebar width with pillarboxing, so the layout stays stable.
17. As a creator, I want horizontal previews (Long-form, X) to scale within the sidebar width with letterboxing, so the layout stays stable.
18. As a creator, I want to see a fallback preview (hooks in a platform frame) when no adaptation exists for Shorts or TikTok, so the sidebar isn't empty before generation.
19. As a creator, I want to see a "Generate adaptation to preview" prompt for Long-form and X when no adaptation exists, so I know these surfaces need generation first.
20. As a creator, I want the preview to upgrade seamlessly from fallback to full preview when an adaptation is generated, so I don't need to refresh or navigate.
21. As a creator, I want non-visual features (tags, hashtags, captions, shorts_link) to remain as CopyBlock panels in the adaptation studio, so they're still accessible for copy-paste.
22. As a creator, I want the preview to render client-side from feature JSON, so no new backend endpoints are needed for visual rendering.
23. As a creator, I want the clip endpoint to return merged clip-level and adaptation-level data in one fetch, so the preview has everything without multiple requests.
24. As a creator, I want the preview to show 3 YouTube Shorts thumbnail variants (one large, two small), so I can see all Test & Compare options at a glance.
25. As a creator, I want the preview to be a static visual render with no interactivity, so it's fast and focused on previewing, not editing.

## Implementation Decisions

### Backend

**Extend `GET /clips/{id}` response** to include a `latest_adaptations` field: a list of `{platform, surface, status, features, assets}` summaries for each adaptation that exists for this clip. The frontend fetches one endpoint instead of two (clip + adaptations). The field is `null` when no adaptations exist.

No new database tables or migrations. The data already exists in `clip_adaptations`; the clip endpoint simply joins it.

### Frontend — Component Architecture

**Surface-specific preview components** (one per platform-surface), each accepting typed props mirroring the backend Pydantic models:

- `YouTubeShortsPreview` — receives `thumbnail_briefs: ThumbnailBrief[]`, `platform_hooks: string[]`, `assets: AdaptationAssets | null`
- `YouTubeLongFormPreview` — receives `chapters: ChapterItem[]`, `poll: CommunityPoll`, `quiz: QuizItem[]`, `thumbnail_briefs: ThumbnailBrief[]`, `shorts_link: string`
- `TikTokPreview` — receives `overlay_spec: OverlaySpecItem[]`, `caption_style: string`, `stickers: StickerSuggestion[]`, `pinned_comment: string`
- `XPreview` — receives `caption: string`, `hashtags: string[]`

Components live in `frontend/components/previews/`. Each component renders a platform-labeled frame with moderate visual fidelity (colored border, platform name badge, no device chrome).

**Fallback rendering:**
- Shorts/TikTok: hook strings rendered inside a minimal platform-colored frame
- Long-form/X: empty frame with "Generate adaptation to preview" prompt

**Layout:**
- The sidebar remains fixed-width (1/3 on desktop)
- The preview scales to fit within the sidebar (pillarboxing for vertical, letterboxing for horizontal)
- Virality gauge stays above the preview card
- Preview tabs match adaptation studio tabs exactly (4 surfaces)

**Copy in preview:**
- Each visual element (hook, poll question, caption, hashtag) has a subtle copy icon on hover
- Copy writes the element text to clipboard
- Non-visual features (tags, hashtags, captions, shorts_link) remain as CopyBlock panels in the adaptation studio

### Adaptation Studio Changes

The `manifestPanels()` function is split:
- **Visual features** (hooks, polls, quizzes, overlays, stickers, chapters, thumbnails) → removed from CopyBlock grid, rendered by preview canvas instead
- **Non-visual features** (tags, hashtags, captions, shorts_link) → remain as CopyBlock panels

The adaptation studio retains: generate button, status badge, asset grid (thumbnails, SRT, chapters downloads), publish checklist, Test & Compare button.

## Testing Decisions

- **Component tests** for each preview component: given a feature JSON object, assert the correct visual elements render (poll options visible, overlay text at placement, hashtag pills present)
- **Fallback tests**: assert fallback rendering when adaptation data is null (hook strings in frame for Shorts/TikTok, generate prompt for Long-form/X)
- **Copy tests**: assert clipboard receives correct text when copy icon is clicked
- **Layout tests**: assert sidebar width doesn't change when switching tabs
- **Integration test**: assert preview upgrades from fallback to full preview when adaptation data arrives
- Prior art: existing `clip-studio.test.tsx` and `adaptation-studio.test.tsx` cover similar component rendering

## Out of Scope

- Interactivity (animations, gesture handling, vote simulation, answer reveal)
- Backend rendering of preview images (all rendering is client-side)
- Dashboard preview thumbnails or teasers
- Editing hooks/features in the preview canvas
- Phone/device chrome mockups (status bars, navigation)
- Real-time hook retention testing or A/B simulation in the preview

## Further Notes

The preview canvas is the visual manifestation of the "platform adaptation" theme. It transforms the hook pane from a JSON viewer into something that feels like each platform's native creator studio — without the complexity of an interactive editor. The goal is: generate, see it, use it.
