# 03 — YouTube Long-form preview

**What to build:** `YouTubeLongFormPreview` renders a horizontal frame with platform label, showing poll as a visual card (question + options), quiz as a question-and-answer card, chapters as a timestamped list, and shorts link. Fallback: "Generate adaptation to preview" prompt when no adaptation exists.

**Blocked by:** 02 — Preview canvas scaffold + YouTube Shorts preview

**Status:** done

- [x] Create `YouTubeLongFormPreview` component in `frontend/components/previews/`
- [x] Accept typed props: `chapters: ChapterItem[]`, `poll: CommunityPoll`, `quiz: QuizItem[]`, `thumbnail_briefs: ThumbnailBrief[]`, `shorts_link: string`
- [x] Render poll card: question as heading, options as a list with radio-button-style bullets
- [x] Render quiz card: question as heading, answer revealed below (static, no animation)
- [x] Render chapters list: chapter titles with timestamps (formatted as M:SS)
- [x] Render shorts link as a styled link or badge
- [x] Horizontal frame with letterboxing to fit sidebar width
- [x] Platform label ("YouTube Video") and colored frame
- [x] Fallback: empty frame with "Generate adaptation to preview" text when no adaptation features exist
- [x] Copy icons on poll question and chapter titles
- [x] Component tests: renders poll/quiz/chapters when features exist, renders fallback when empty
