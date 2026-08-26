# 04 — TikTok preview

**What to build:** `TikTokPreview` renders a vertical 9:16 frame with platform label, showing overlay text at placement positions, sticker emoji at their positions, and pinned comment as a static bubble below the frame. Fallback: hook strings in a TikTok-colored frame when no adaptation exists.

**Blocked by:** 02 — Preview canvas scaffold + YouTube Shorts preview

**Status:** ready-for-agent

- [ ] Create `TikTokPreview` component in `frontend/components/previews/`
- [ ] Accept typed props: `overlay_spec: OverlaySpecItem[]`, `caption_style: string`, `stickers: StickerSuggestion[]`, `pinned_comment: string`
- [ ] Render vertical 9:16 frame with TikTok-colored border and "TikTok" label
- [ ] Render overlay text at specified placement positions (top/center/bottom) with specified style (bold/outlined/italic)
- [ ] Render sticker emoji at their placement positions
- [ ] Render pinned comment as a chat-bubble-style element below the frame
- [ ] Render caption style note below the frame
- [ ] Pillarboxing to fit sidebar width
- [ ] Fallback: hook strings from `suggested_hooks.platform_hooks.tiktok` inside a TikTok-colored frame
- [ ] Copy icons on overlay text and pinned comment
- [ ] Component tests: renders overlays/stickers/pinned comment when features exist, renders fallback when empty
