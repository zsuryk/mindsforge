# 12 — Adaptation assets & rendering

**What to build:** Turn part of the adaptation manifest into real downloadable files, served over `/media` like clips:

- **Thumbnail variants:** for each of the 3 Test & Compare briefs, extract a frame from the clip's source at the Mind-chosen timestamp (reuse `media.extract_frame_at_timestamp`), center-crop to the surface aspect ratio (16:9 1280×720 for youtube LONG_FORM, 9:16 1080×1920 for SHORTS/tiktok), composite the overlay text via Pillow (new dependency `pillow`) with a basic style choice from the brief (e.g., bold/outlined caption zones), write `media/adaptations/{adaptation_id}/thumb_{i}.png`.
- **Captions:** SRT file from the clip's transcript segments — the clip window is derived by filtering `job.transcript_segments` to `[clip.start_time, clip.end_time]` (segments currently live on the job; clip does not store its own) — `captions.srt`.
- **Chapters:** chapter list file with timestamps, from the same filtered segments — `chapters.txt` (used for youtube LONG_FORM).
- Assets are recorded on the adaptation row (`assets` JSON: thumbnail_variants [{id, file_path}], captions_file, chapters_file) with `media_url` served URLs; the UI (ticket 13) downloads/previews them.

**Blocked by:** 11 — Adaptation domain & lazy generation

**Status:** done (e7aa4f0)

- [x] `pillow` added to `pyproject.toml`
- [x] Thumbnail renderer: frame extract + center-crop + text overlay per surface aspect ratio; deterministic output, error → adaptation FAILED
- [x] SRT + chapters writers from filtered job segments (offset to clip-relative timestamps for SRT; absolute for chapters)
- [x] Assets JSON persisted with servable URLs; renders run inside the generation task after the manifest is accepted
- [x] Tests: aspect-ratio crops, overlay text present (pixel/smoke checks), SRT segment offsets/format, chapters file content, media_url serving, failure paths