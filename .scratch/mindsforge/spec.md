# MindsForge — Implementation Plan

AI-driven creator platform: automatically identifies high-converting short clips from long-form video/audio, creates platform-specific content variants, executes autonomous A/B testing, and manages persistent creator memory via Minds by Animoca Brands.

## Architecture

Decoupled system: Next.js 14 App Router frontend (TypeScript strict, Tailwind 3.4+, Shadcn UI, Lucide, Recharts) + FastAPI async backend (SQLAlchemy 2.0 + SQLite, no Redis) + FFmpeg/Groq Whisper media pipeline + Minds Builder API agent engine.

**Stack:** Next.js 14.2+, Python 3.11+, FastAPI 0.110+, SQLAlchemy 2.0+ with Alembic, system FFmpeg 6.0+, Groq SDK (`whisper-large-v3`), `@animocabrands/minds-cli`.

**Decisions made during planning (supersede original plan):**

1. **No Redis.** Plan listed REDIS_URL + docker-compose Redis but no code consumes it. Job processing runs as FastAPI background tasks; the A/B cron is an async loop.
2. **yt-dlp for downloads.** YouTube Data API v3 cannot download video files; use yt-dlp for source-URL ingestion. Drop YOUTUBE_CLIENT_ID/SECRET from the MVP.
3. Jobs accept either a `source_url` (downloaded via yt-dlp) or a direct file upload.

## Environment config

**Backend:** `HOST`, `PORT`, `DATABASE_URL` (`sqlite:///./mindsforge.db`), `MINDS_BUILDER_API_KEY`, `MINDS_AGENT_ID`, `GROQ_API_KEY`.

**Frontend:** `NEXT_PUBLIC_API_URL` (`http://localhost:8000/api/v1`), `NEXT_PUBLIC_WS_URL` (`ws://localhost:8000/ws`).

## Database

- **jobs**: id (UUID4), title, source_url?, file_path?, status enum (PENDING, DOWNLOADING, TRANSCRIBING, EXTRACTING_CLIPS, COMPLETED, FAILED), duration_seconds?, error_message?, created_at, updated_at.
- **clips**: id (UUID4), job_id FK, title, start_time, end_time, transcript_text, file_path, virality_score (0–100), suggested_hooks (JSON), created_at.
- **ab_experiments**: id (UUID4), clip_id FK, platform, status enum (ACTIVE, CONCLUDED, FAILED), variants (JSON array: variant_id, title, thumbnail_path, ctr, views), winning_variant_id?, learned_insight?, created_at, concluded_at?.

## Minds agent protocol

Memory context: `creator_id`, `brand_voice`, `historical_insights` (per-platform: youtube title patterns/durations/hooks, tiktok pacing/captions), `ab_test_history` (list of outcome records).

Service calls to `https://build.hellominds.ai/api/v1` with `MINDS_BUILDER_API_KEY` header:

- `GET /minds/{agent_id}/memory` → context tree
- `POST /minds/{agent_id}/memory/update` → persist insight key/value
- `generate_clip_metadata(transcript)` → LLM prompt returns structured JSON: `virality_score`, `suggested_titles`, `platform_hooks`

## Services

- **Media:** `extract_audio` (16kHz mono WAV), `cut_clip` (fast-seek `-ss`/`-t`, H.264 MP4), `extract_frame_at_timestamp` (PNG thumbnail).
- **Transcription:** Groq `whisper-large-v3` with `verbose_json` → segments with start/end.
- **A/B cron worker:** every 60s, for each ACTIVE experiment update variant views/CTR (simulated), conclude when cumulative views ≥ 1,000, pick highest CTR, write `learned_insight` to Minds persistent memory.

## API (`/api/v1`)

- `POST /jobs/process` → 202 with job_id, status, message (async pipeline)
- `GET /jobs/{job_id}` → job state
- `GET /jobs/{job_id}/clips` → clips with virality, file URLs, hooks; `GET /clips/{clip_id}`
- `POST /ab-tests/start` → 201 experiment; `GET /ab-tests/active`
- `GET /agent/memory` → {agent_id, memory}; `POST /agent/memory/update` → success boolean

## Frontend pages (dark `bg-slate-950` base)

- `/` dashboard: header + URL input bar, four metric cards (Total Clips, Active A/B Tests, Avg Virality, Total Insights), recent jobs table with status badges.
- `/jobs`: job list + submission form.
- `/clips/[id]`: studio — video player, virality gauge, platform hook tabs, "Launch A/B Test" modal.
- `/ab-experiments`: variant cards, Recharts CTR comparison, concluded insight banner.
- `/memory-inspector`: brain icon header, refresh button, insight cards grid, syntax-highlighted JSON tree viewer.

## Build phases (ticket graph)

Ticket graph below in `issues/`. Slices: skeleton → ingestion → transcription → clip extraction → Minds scoring + clip studio → memory inspector → autonomous A/B testing → overview dashboard.