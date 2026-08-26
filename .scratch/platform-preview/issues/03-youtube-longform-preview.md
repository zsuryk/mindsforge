# 03 — YouTube Long-form preview

**What to build:** `YouTubeLongFormPreview` renders a horizontal frame with platform label, showing poll as a visual card (question + options), quiz as a question-and-answer card, chapters as a timestamped list, and shorts link. Fallback: "Generate adaptation to preview" prompt when no adaptation exists.

**Blocked by:** 02 — Preview canvas scaffold + YouTube Shorts preview

**Status:** ready-for-agent

- [ ] Create `YouTubeLongFormPreview` component in `frontend/components/previews/`
- [ ] Accept typed props: `chapters: ChapterItem[]`, `poll: CommunityPoll`, `quiz: QuizItem[]`, `thumbnail_briefs: ThumbnailBrief[]`, `shorts_link: string`
- [ ] Render poll card: question as heading, options as a list with radio-button-style bullets
- [ ] Render quiz card: question as heading, answer revealed below (static, no animation)
- [ ] Render chapters list: chapter titles with timestamps (formatted as M:SS)
- [ ] Render shorts link as a styled link or badge
- [ ] Horizontal frame with letterboxing to fit sidebar width
- [ ] Platform label ("YouTube Video") and colored frame
- [ ] Fallback: empty frame with "Generate adaptation to preview" text when no adaptation features exist
- [ ] Copy icons on poll question and chapter titles
- [ ] Component tests: renders poll/quiz/chapters when features exist, renders fallback when empty
