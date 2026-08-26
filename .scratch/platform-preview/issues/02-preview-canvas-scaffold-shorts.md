# 02 — Preview canvas scaffold + YouTube Shorts preview

**What to build:** Replace the "Platform hooks" card in the clip studio sidebar with a `PlatformPreviewCanvas` component. The canvas has 4 tabs matching the adaptation studio tabs (YouTube Shorts, YouTube Video, TikTok, X). The virality gauge stays above the preview. The sidebar remains fixed-width (1/3 on desktop); previews scale to fit (pillarbox/letterbox). First surface: `YouTubeShortsPreview` renders 3 thumbnail variants (1 large + 2 small) with hook overlay text from the merged clip data. Fallback state: hook strings in a YouTube-colored frame when no adaptation exists.

**Blocked by:** 01 — Extend clip endpoint with adaptation summaries

**Status:** done

- [x] Create `frontend/components/previews/` directory
- [x] Create `PlatformPreviewCanvas` component: receives `clip` (with `suggested_hooks` and `latest_adaptations`), renders virality gauge above a tabbed preview area
- [x] Wire `PlatformPreviewCanvas` into clip studio page (`app/clips/[id]/page.tsx`), replacing the "Platform hooks" card in the sidebar
- [x] Tabs match adaptation studio exactly: YouTube Shorts, YouTube Video, TikTok, X
- [x] Sidebar layout: virality gauge → preview canvas, fixed width, preview scales to fit
- [x] Create `YouTubeShortsPreview` component: vertical frame with platform label, renders 3 thumbnail variants (1 large + 2 small) when adaptation assets exist, hook overlay text on each
- [x] Fallback: when no adaptation exists for Shorts, render hook strings from `suggested_hooks.platform_hooks.youtube_shorts` inside a YouTube-colored frame
- [x] Add copy icon on hover for hook text elements
- [x] Add component tests for `YouTubeShortsPreview`: renders thumbnails when assets exist, renders hook fallback when no adaptation
- [x] Add component test for `PlatformPreviewCanvas`: tabs render, virality gauge visible, layout stable on tab switch
