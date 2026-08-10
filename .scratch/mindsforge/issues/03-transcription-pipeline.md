# 03 — Transcription pipeline

**What to build:** The first real processing leg. After a job is submitted, a background task picks it up and advances it through DOWNLOADING → TRANSCRIBING: it downloads the source (yt-dlp for URLs, or uses the uploaded file), extracts a 16kHz mono WAV with FFmpeg, sends it to Groq Whisper (`whisper-large-v3`, verbose JSON), and persists the timed transcript segments on the job. Failures anywhere set the job to FAILED with an error message instead of crashing the process.

**Blocked by:** 02 — Job ingestion

**Status:** ready-for-agent

- [ ] A submitted job starts processing automatically in the background and its status transitions through DOWNLOADING and TRANSCRIBING
- [ ] URL jobs download via yt-dlp into raw storage; upload jobs read the local file
- [ ] FFmpeg audio extraction produces a Whisper-ready 16kHz mono WAV
- [ ] Groq transcription returns segments with text, start, and end times, stored on the job
- [ ] Any stage failure leaves the job FAILED with a descriptive error message, and the pipeline stops cleanly
- [ ] A short real video (e.g. a few minutes) can be transcribed end-to-end; the UI shows the live status transition