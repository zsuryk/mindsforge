# MindsForge — Implementation Plan

AI-driven creator platform: automatically identifies high-converting short clips from long-form video/audio, packages each clip into platform-native adaptations (thumbnails, captions, chapters, tags, polls, quizzes, stickers, hooks), executes autonomous A/B testing, and manages persistent creator memory via Minds by Animoca Brands.

## Architecture

Decoupled system: Next.js 14 App Router frontend (TypeScript strict, Tailwind 3.4+, Shadcn UI, Lucide, Recharts) + FastAPI async backend (SQLAlchemy 2.0 + SQLite, no Redis) + FFmpeg/Groq Whisper media pipeline + Minds Builder API agent engine.

**Stack:** Next.js 14.2+, Python 3.11+, FastAPI 0.110+, SQLAlchemy 2.0+ with Alembic, system FFmpeg 6.0+, Groq SDK (`whisper-large-v3`), `@animocabrands/minds-cli`.

**Decisions made during planning (supersede original plan):**

1. **No Redis.** Plan listed REDIS_URL + docker-compose Redis but no code consumes it. Job processing runs as FastAPI background tasks; the A/B cron is an async loop.
2. **yt-dlp for downloads.** YouTube Data API v3 cannot download video files; use yt-dlp for source-URL ingestion. Drop YOUTUBE_CLIENT_ID/SECRET from the MVP.
3. Jobs accept either a `source_url` (downloaded via yt-dlp) or a direct file upload.
4. **Adaptations are manifests, not published posts.** No platform API publishing (see ADR-0001). The Mind authors features; code renders assets; the creator publishes manually via a checklist.
5. **Fail-closed Minds integration** (ADR-0002): scoring failures fail the job; conclusion-time Mind failure fails the experiment. No silent fallbacks.

## Environment config

**Backend:** `HOST`, `PORT`, `DATABASE_URL` (`sqlite:///./mindsforge.db`), `MINDS_BUILDER_API_KEY`, `MINDS_AGENT_ID`, `GROQ_API_KEY`, `TAVILY_API_KEY` (chat trend research; fail-closed without it).

**Frontend:** `NEXT_PUBLIC_API_URL` (`http://localhost:8000/api/v1`), `NEXT_PUBLIC_WS_URL` (`ws://localhost:8000/ws`).

## Database

- **jobs**: id (UUID4), title, source_url?, file_path?, status enum (PENDING, DOWNLOADING, TRANSCRIBING, EXTRACTING_CLIPS, COMPLETED, FAILED), duration_seconds?, error_message?, created_at, updated_at.
- **clips**: id (UUID4), job_id FK, title, start_time, end_time, transcript_text, file_path, virality_score (0–100), suggested_hooks (JSON), created_at.
- **ab_experiments**: id (UUID4), clip_id FK, platform, variant_kind enum (TITLE, THUMBNAIL), status enum (ACTIVE, CONCLUDED, FAILED), data_source enum (SIMULATED, MANUAL, default SIMULATED), variants (JSON array: variant_id, title, thumbnail_path, ctr, views, clicks), winning_variant_id?, learned_insight?, error_message?, created_at, concluded_at?. The winner is decided by the Mind at conclusion.
- **clip_adaptations**: id (UUID4), clip_id FK, platform, surface enum (SHORTS, LONG_FORM, POST), status enum (PENDING, GENERATING, READY, FAILED), features (JSON: chapters, tags, polls, quizzes, stickers, pinned_comment, overlay_spec, shorts_link, platform_hooks), assets (JSON: thumbnail_variants [{id, frame_timestamp, overlay_text, file_path}], captions_file, chapters_file), contents? error_message?, created_at, updated_at.
- **mind_activity**: id (UUID4), event_type (String(64), free-form), label (String(255)), detail (JSON nullable), ref_id (String(64) nullable), created_at. Logged by every Mind-touching service (scoring, experiment sweeps/conclusions, adaptations, trend research, chat rule saves, notifications); trimmed to the newest 500 rows on insert.

## Minds agent protocol

Memory context: `creator_id`, `brand_voice`, `historical_insights` (per-platform: youtube title patterns/durations/hooks, tiktok pacing/captions), `ab_test_history` (list of outcome records).

Service calls to `https://build.hellominds.ai/api/v1` with `MINDS_BUILDER_API_KEY` header:

- `GET /minds/{agent_id}/memory` → context tree
- `POST /minds/{agent_id}/memory/update` → persist insight key/value
- `generate_clip_metadata(transcript)` → LLM prompt returns structured JSON: `virality_score`, `suggested_titles`, `platform_hooks`
- `decide_experiment_winner(platform, variants)` → LLM prompt returns structured JSON: `winning_variant_id`, `reasoning` (becomes `learned_insight`)
- `generate_adaptation_features(clip, platform, surface, segments, memory_context)` → LLM prompt returns the feature manifest JSON (per surface: tags, polls, quizzes, sticker placement, pinned comment, overlay styles, thumbnail briefs, shorts-link target)
- Memory keys currently consumed: `creator_id`, `brand_voice`, `historical_insights`, `ab_test_history`, `brand_rules` (creator preferences extracted from chat, bounded to 50), `trend_research` (chat research results, bounded to 10); adaptations append `adaptation_history` (per-surface records of what features were produced). All keys reach every generation prompt via `MEMORY_CONTEXT_KEYS` + `build_memory_context` (with `MEMORY_CONTEXT_VALUE_LIMIT` truncation as safety net).
- Chat uses a separate `mindsforge-chat` alias (`CHAT_ALIAS`) with a 180s reply timeout — never mixed with scoring/adaptation conversations. App-posted messages (notifications, trend results, initialisation) are prefixed with `SYSTEM_MARKER = "[MindsForge] "` so the UI can render them as system chips; the Mind reads them as normal thread content and remembers outcomes natively.

## Services

- **Media:** `extract_audio` (16kHz mono WAV), `cut_clip` (fast-seek `-ss`/`-t`, H.264 MP4), `extract_frame_at_timestamp` (PNG thumbnail).
- **Transcription:** Groq `whisper-large-v3` with `verbose_json` → segments with start/end.
- **Scoring hard gate:** scoring is fail-closed — Minds unconfigured fails the job fast; any scoring MindsError fails the job (no unscored clips).
- **A/B cron worker:** every 60s, for each ACTIVE experiment update variant views/CTR (simulated), conclude when cumulative views ≥ 1,000, ask the Mind to pick the winner and author `learned_insight`; write it to Minds persistent memory. Experiments with `data_source=MANUAL` are skipped entirely (real numbers never accumulate simulated traffic) but still conclude at the threshold. Mind failure at conclusion → experiment FAILED with error_message. Conclusions and failures post a `[MindsForge]`-marked notification into the chat thread (`notify_mind`, best-effort — a notification failure never fails the experiment).
- **Chat:** `POST /chat/messages` sends the user's message on `mindsforge-chat` and polls for the first Mind reply (senderType 0) newer than the history cursor, 2s interval / 180s timeout (`minds.send_chat_message`); empty conversations are seeded once with a system-marked strategist instruction. `GET /chat/history` maps the thread to roles (senderType 0 → mind, `[MindsForge]`-marked senderType 1 → system with marker stripped, else user). No app-side chat table — the conversation is native Minds persistence. Minds unconfigured or any MindsError → 502 (fail-closed per ADR-0002).
- **Trend research:** `POST /chat/trends` searches Tavily (`TAVILY_API_KEY`, basic depth, ≤5 results), appends to the `trend_research` memory key (last 10), posts a marked "Researched '<query>'…" message into the chat thread, returns results for the UI chip. The inline trigger `/search (?:for|trends? in|trends? for) (.+)/i` in a chat message runs the same search-and-notify before the user message. Adaptations only: `adaptations._memory_context` appends the latest 5 entries within 7 days (content truncated ~200 chars); scoring prompts stay untouched. Unconfigured Tavily → 502.
- **Brand-rule sidecar:** `extract_brand_rules` (Groq, strict extraction prompt) runs on every user chat message; detected preferences append to `brand_rules` (bounded to 50, `source: "chat"`) and return as `rules` for the "saved to your Mind" chip. Extraction failure is non-blocking (message still sent, `rules: []`, failure logged).
- **Activity log:** `activity.log(event_type, label, detail=None, ref_id=None)` — one row per Mind-touching event (clip scored, experiment sweep/conclusion/failure, adaptation ready/failed, trend researched, rule saved, mind notified); never raises into callers; table trimmed to newest 500 rows.
- **Adaptations (lazy):** per clip + platform-surface, generated on demand via `POST /clips/{id}/adaptations/{platform}/{surface}`: Mind authors the feature manifest (with memory context), code renders assets (thumbnail variants via Pillow onto ffmpeg-extracted frames at surface aspect ratio; SRT captions + chapter list derived from job transcript segments filtered to the clip window), status PENDING→GENERATING→READY|FAILED, success appends an `adaptation_history` record to Minds memory.

## API (`/api/v1`)

- `POST /jobs/process` → 202 with job_id, status, message (async pipeline)
- `GET /jobs/{job_id}` → job state
- `GET /jobs/{job_id}/clips` → clips with virality, file URLs, hooks; `GET /clips/{clip_id}`
- `POST /ab-tests/start` → 201 experiment (now accepts `variant_kind` TITLE|THUMBNAIL; thumbnail variants reference rendered assets); `GET /ab-tests/active` (rows include `data_source`); `PATCH /ab-tests/{experiment_id}/variants/{variant_id}` `{views, clicks}` → 200 updated experiment (recomputes CTR, flips experiment to `data_source=MANUAL`; 404 unknown ids, 422 non-ACTIVE/negative/clicks > views)
- `GET /agent/memory` → {agent_id, memory}; `POST /agent/memory/update` → success boolean
- `POST /chat/messages {message}` → 200 `{reply, rules}` (fail-closed 502); `GET /chat/history` → 200 `{messages: [{role, text, fingerprint}]}`; `POST /chat/trends {query, platform?}` → 200 `{results}`
- `GET /dashboard/stats`; `GET /dashboard/activity?limit=20` → newest-first activity rows
- `GET /clips/{clip_id}/adaptations` → list per platform-surface with status, features, asset URLs; `POST /clips/{clip_id}/adaptations/{platform}/{surface}` → 202, triggers lazy generation (background task, cached: re-request of READY/PENDING returns current row); `GET /clips/{clip_id}/adaptations/{id}` → row detail

## Frontend pages (dark `bg-slate-950` base)

- `/` dashboard: header + URL input bar, four metric cards (Total Clips, Active A/B Tests, Avg Virality, Total Insights), "Mind at Work" activity panel (icon per event type, relative time, 5s polling, newest event highlighted), "What your Mind remembers" persistence card (brand voice excerpt, latest 3 brand rules, latest 3 learned insights, latest 2 trend queries, with ages; link to `/memory-inspector`), recent jobs table with status badges.
- `/jobs`: job list + submission form.
- `/clips/[id]`: studio — video player, virality gauge, platform hook tabs, platform-surface adaptation tabs (generate button + status, feature manifest with copy-paste blocks, asset downloads: thumbnail variant grid, SRT, chapter list; publish checklist; Test & Compare launches an experiment with `variant_kind=THUMBNAIL`), "Launch A/B Test" modal (title or thumbnail variants).
- `/ab-experiments`: variant cards with simulated/manual badge, Recharts CTR comparison, concluded insight banner, inline per-variant views/clicks editing for ACTIVE experiments (PATCH flips the card to manual).
- `/chat`: full chat UI with the Mind — user bubbles / Mind replies / system chips (marker stripped), rule-saved chips, trend chips, "Research trends" input, "your Mind is thinking…" state, 5s history polling (catches background notifications), fail-closed 502 error banner, welcome empty state.
- `/memory-inspector`: brain icon header, refresh button, insight cards grid, syntax-highlighted JSON tree viewer.

## Build phases (ticket graph)

Ticket graph below in `issues/`. Slices: skeleton → ingestion → transcription → clip extraction → Minds scoring + clip studio → memory inspector → autonomous A/B testing → overview dashboard → Mind-decided A/B conclusion (09) + scoring hard gate (10) → adaptation domain & lazy generation (11) → adaptation assets & rendering (12) → adaptation studio UI (13).

Blocking: 09 and 10 are independent of each other (each modifies shipped behavior: ticket 07 conclusion, tickets 04/05 scoring). 10 → 11 → 12; 13 is blocked by 09, 11 and 12.

Post-review scope (chat, trends, autonomy — tickets 15–22) in the section below; its behaviour is folded into the sections above.

## Post-review scope: chat, trends, and autonomy (tickets 15–22)

Decided by grilling (2026-08-20). Four additions that deepen the Mind-integrality
story for the hackathon: a creator-facing Chat with the Mind, trend research,
visible background execution, and a real-data feedback path for experiments.

- **Chat (15, 17, 18, 19):** `/chat` is a real conversation with the Mind via the
  messaging API on a dedicated `mindsforge-chat` alias (180s reply timeout,
  history loads the thread; chat never mixes with scoring conversations). The
  Mind remembers natively from the thread — no app-side memory injection. A
  Groq extraction sidecar detects brand-rule statements in chat and appends them
  to a `brand_rules` memory key (structured list, injected into every generation
  prompt via `MEMORY_CONTEXT_KEYS`). `notify_mind` posts `[MindsForge]`-marked
  messages into the chat thread when an Experiment concludes or an Adaptation is
  generated, so the Mind learns outcomes from its own conversation; the UI
  renders marked messages as system chips.
- **Trend research (16):** app-side Tavily (`TAVILY_API_KEY`) searched from the
  chat ("Research trends" button or "search trends for X" trigger); results are
  saved to a `trend_research` memory key (last 10) and posted into the chat
  thread as a system chip. The last 5 entries within 7 days are appended to
  adaptation-generation prompts (adaptations only — scoring stays untouched).
  The Mind may additionally use its own Tavily connection when asked open-ended
  questions (best-effort, instructed at chat initialisation).
- **Mind at Work feed (20):** a `mind_activity` table logged by every
  Mind-touching service (scoring, experiment sweeps/conclusions, adaptations,
  research, chat) and surfaced as a 5s-polled dashboard panel — the A/B worker
  becomes a visible 24/7 heartbeat.
- **Persistence recap (21):** a "What your Mind remembers" dashboard card
  rendering brand voice, recent brand rules, learned insights and trend research
  from the memory tree, plus a scripted day-1 → day-2 persistence demo in the
  README.
- **Real-data feedback (22):** experiments gain `data_source`
  (SIMULATED|MANUAL); `PATCH /ab-tests/{id}/variants/{variant_id}` lets the
  creator enter real views/clicks (experiment flips to MANUAL and the simulation
  worker skips it), so a published clip can conclude on real data.

Environment: adds `TAVILY_API_KEY`. Memory keys: adds `brand_rules`,
`trend_research`. Migrations: 0006 (data_source), 0007 (mind_activity).

Blocking: 19 is blocked by 15, 16 and 17; 16 and 17 are blocked by 15 (they hook
into `POST /chat/messages` and the system-marker convention); 18 is blocked by
15. 20, 21 and 22 are independent.