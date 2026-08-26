# 06 — Adaptation studio cleanup + copy-in-preview

**What to build:** Remove visual feature CopyBlocks (hooks, polls, quizzes, overlays, stickers, chapters, thumbnails) from the adaptation studio's manifest panel grid. Non-visual features (tags, hashtags, captions, shorts_link) remain as CopyBlock panels. Copy icons on preview elements are wired to clipboard.

**Blocked by:** 03 — YouTube Long-form preview, 04 — TikTok preview, 05 — X preview

**Status:** ready-for-agent

- [ ] Update `manifestPanels()` in `frontend/components/adaptation-studio.tsx` to exclude visual feature keys: `platform_hooks`, `poll`, `quiz`, `stickers`, `pinned_comment`, `overlay_spec`, `caption_style`, `chapters`, `thumbnail_briefs`
- [ ] Keep non-visual CopyBlock panels: `tags`, `hashtags`, `caption`, `shorts_link`
- [ ] Verify adaptation studio still renders correctly with reduced panel set
- [ ] Wire copy icons in preview components to `navigator.clipboard.writeText()`
- [ ] Add copy feedback (brief "Copied" tooltip or icon change) on preview copy icons
- [ ] Update existing `adaptation-studio.test.tsx` to reflect removed panels
- [ ] Add test: preview copy icons write correct text to clipboard
