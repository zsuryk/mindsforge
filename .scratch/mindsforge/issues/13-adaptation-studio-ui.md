# 13 — Adaptation studio UI

**What to build:** The studio (`app/clips/[id]/page.tsx`) gains platform-surface adaptation tabs (YouTube Shorts, YouTube Video, TikTok, X). Each tab: platform/platform-surface selector, generate button + status badge (PENDING/GENERATING/READY/FAILED with error), then when READY:

- **Feature manifest panels** with copy-paste blocks: chapters + timestamps, tags (chips), poll (question + options), quiz, sticker suggestions, pinned comment, overlay styles, shorts-link target, X caption + hashtags
- **Asset previews/downloads:** thumbnail variant grid (3 up), SRT and chapters file download links (served from `/media`)
- **Publish checklist:** per-surface step list the creator ticks off (e.g., "upload video → paste chapters → add tags → run Test & Compare")
- **Test & Compare:** for youtube surfaces, "Run Test & Compare" launches the A/B modal with `variant_kind=THUMBNAIL` pre-filled from the 3 rendered variants (experiments page already renders variants; thumbnail variants show image instead of title-only, and the modal from ticket 05 gains a title|thumbnail toggle)

Platforms list (`frontend/lib/platforms.ts`) gains the surfaces; API client (`frontend/lib/api.ts`) gains the adaptation endpoints. Update `clip-studio.test.tsx` accordingly.

**Blocked by:** 09 — Mind-decided A/B conclusion, 11 — Adaptation domain & lazy generation, 12 — Adaptation assets & rendering

**Status:** ready-for-agent

- [ ] Surfaces in a shared frontend constant; adaptation tabs render per platform-surface
- [ ] Generate button + status lifecycle polling (or refresh-on-click) + FAILED error display
- [ ] Manifest panels with copy-paste blocks for every feature type
- [ ] Thumbnail variant grid + SRT/chapters download links
- [ ] Publish checklist component
- [ ] A/B modal toggle title|thumbnail; thumbnail-variant experiment launches with `variant_kind=THUMBNAIL`; experiments page renders thumbnail variants
- [ ] Vitest coverage for the new components