# 04 — Clip extraction

**What to build:** From transcript to short clips. The processing pipeline continues from TRANSCRIBING to EXTRACTING_CLIPS: the timed transcript is split into candidate segments (sentence-boundary chunks within short-form duration bounds), each segment is cut from the source video with fast-seek FFmpeg into an H.264 MP4, a thumbnail frame is captured, and each clip persists as its own record with title, times, transcript text, and paths. The clips endpoint returns them, and the frontend lists a job's clips with playable previews.

**Blocked by:** 03 — Transcription pipeline

**Status:** ready-for-agent

- [ ] Transcript segments split into candidate clips (short-form duration bounds, sentence-boundary aware)
- [ ] Each candidate is cut into an MP4 (re-encoded H.264) and gets a thumbnail frame extraction
- [ ] Clip records persist with all spec fields; job transitions to COMPLETED when clips are done
- [ ] Clips endpoint returns clips for a job; clip detail endpoint works
- [ ] Jobs page shows a job's extracted clips with an HTML5 video preview
- [ ] A full run on the T3 test video yields playable clips with thumbnails