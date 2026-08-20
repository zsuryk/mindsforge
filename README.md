# MindsForge

**Turn long-form videos into high-converting short clips — automatically.**

MindsForge is an AI-powered creator platform that:

- **Finds the golden moments** — scans long-form video/audio and identifies the most viral-worthy short clips.
- **Adapts for every platform** — generates platform-specific variants of each clip.
- **A/B tests by itself** — launches experiments and tracks which variant wins.
- **Chats with the creator** — ask it anything, state brand rules ("always use bold captions"), and it researches live trends (Tavily) before answering.
- **Remembers creators** — persistent creator memory via Minds by Animoca Brands, proven at a glance on the dashboard.
- **Works 24/7 in the background** — a live "Mind at Work" feed shows scoring, experiment sweeps, and adaptation generation as they happen.

## What it generates

Every clip is packaged into a downloadable, platform-ready content kit:

| Surface | Rendered thumbnails | Copy & hooks | Chapters & captions | Extras | A/B testing |
|---|---|---|---|---|---|
| **YouTube Shorts** | 3× 1080×1920 PNGs | Platform hooks | — | — | Test & Compare on thumbnails |
| **YouTube Long-form** | 3× 1280×720 PNGs | Tags | `chapters.txt` + SRT | Poll, quiz, Shorts link | Test & Compare on thumbnails |
| **TikTok** | Per-segment overlay renders | Caption style | SRT auto-captions | Stickers, pinned comment | — |
| **X** | — | Caption + hashtags | — | — | — |

Everything renders into real assets (thumbnail PNGs, `captions.srt`, `chapters.txt`) with a per-surface publish checklist in the studio — and every generated package is appended to the creator's persistent memory, so each new generation compounds on past learnings. The dashboard's "What your Mind remembers" card surfaces that memory (brand voice, brand rules, learned insights, trend research) with ages, so persistence needs no explanation.

## Prerequisites

- **uv** — Python package manager
- **Node.js 20+** (LTS recommended)
- **FFmpeg 6+** (in system PATH)
- **API keys** — the Mind is fail-closed without `MINDS_BUILDER_API_KEY` + `MINDS_AGENT_ID` (scoring/memory); contact for the Minds keys or generate one. Transcription runs on Groq by default (`GROQ_API_KEY` — free key at https://console.groq.com), or fully locally with `TRANSCRIPTION_PROVIDER=local` if you're in a region Groq doesn't support — no VPN needed. Chat trend research needs `TAVILY_API_KEY` (free key at https://tavily.com).

## Install the tools

**macOS**

```sh
brew install uv ffmpeg node
```

**Windows**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
winget install --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
winget install --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
```

**Linux (Ubuntu/Debian)**

```sh
sudo apt update && sudo apt install -y ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
```

Verify: `uv --version && node --version && ffmpeg -version`

## Configure

In the `backend` folder:

```sh
cp .env.example .env     # Windows: Copy-Item .env.example .env
```

Fill in the Mind keys, `GROQ_API_KEY` (unless using `TRANSCRIPTION_PROVIDER=local`) and `TAVILY_API_KEY` in `.env`. Everything else has sane defaults.

## Run

**Backend**:

```sh
cd backend
uv sync
uv run --module app
```

Serves on `http://localhost:8000` — health check at `/api/v1/health`.

**Frontend**:

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Demo walkthrough

1. The dashboard shows a live backend status light fed from `/api/v1/health`.
2. Paste a video URL (a YouTube link works) into the box at the top and press **Enter** — the app downloads it, extracts the most viral-worthy short clips with virality scores, and generates platform variants. A few minutes of video take roughly a minute or two to process.
3. Track progress in **Recent jobs** / the **Jobs** sidebar page (`queued` → `processing` → `completed`).
4. Explore the rest: **Clips** (per-clip virality), **A/B Experiments** (launch a test between variants — the platform picks the winner), **Chat** (talk to the Mind, state brand rules, research trends), and **Memory Inspector** (what MindsForge remembers about the creator).

## Persistence demo (5 minutes)

The Mind's memory survives backend restarts — it lives in local SQLite plus the Minds conversation thread. This scripted walkthrough proves it end to end.

**Day 1 — build the memory (~3 min)**

1. Open **Chat** and tell the Mind a brand rule, e.g. *"always use bold captions and never clickbait"* — the reply chip confirms *"Your Mind saved: …"*.
2. Give the Mind a voice to remember: open **Memory Inspector** and write the `brand_voice` key with your style, e.g. `Bold, direct, and generous with practical value.`
3. Ask it to research a trend: *"search trends for hook retention 2026"* (needs `TAVILY_API_KEY`). The results land in the chat as a system note.
4. Open a clip in the **Clips** studio and generate a YouTube Shorts adaptation — the features are written to `adaptation_history`.
5. Launch an **A/B test** on the clip; once the view threshold is reached the Mind picks the winner and writes the insight to memory.
6. Check the dashboard: the **Mind at Work** feed shows rule saves, trend research, and adaptations live; the **What your Mind remembers** card shows the brand voice, rules, insights, and trend queries with ages.

**Day 2 — prove it persisted (~2 min)**

1. Restart the backend (Ctrl+C, then `uv run --module app`). SQLite and the Minds thread survive.
2. Ask the chat *"what's my brand voice?"* and *"what did my experiments teach me?"* — the Mind answers from its thread memory.
3. Generate a new adaptation and watch it follow your saved rule — the rule is fed into the generation prompt.
4. Open **Memory Inspector** — the full accumulated history (rules, trends, insights, adaptations) is all there.

## Troubleshooting

| Problem | Fix |
|---|---|
| Job fails with `Minds is not configured` or `GROQ_API_KEY is not configured` | Keys missing from `backend/.env`, or the backend wasn't restarted after adding them (Ctrl+C, then `uv run --module app`). |
| Trend research fails with `TAVILY_API_KEY is not configured` | Add `TAVILY_API_KEY` to `backend/.env` and restart the backend — trend research is fail-closed without it. |
| Chat shows `Timed out waiting for a Mind reply` | The Mind took longer than 180s to answer — check the Minds keys and that the agent is responsive, then send the message again. |
| `command not found: ffmpeg` / jobs fail with an ffmpeg error | FFmpeg not on PATH — install it per OS and open a new terminal. |
| Port 8000 already in use | Quit the other process, or run with `PORT=8001` and point the frontend's `NEXT_PUBLIC_API_URL` at it. |
| Video fails to download | Some hosts (e.g. YouTube) block automated downloads — use a direct `.mp4` URL instead. |
| Red status light in the header | Backend isn't running — start it (see **Run**). |
| Groq transcription failed: Error code: 403 | Region unsupported by Groq — set `TRANSCRIPTION_PROVIDER=local` in `backend/.env` to transcribe with local Whisper instead (first run downloads the model). |

---

## For contributors

```sh
cd backend && uv run pytest        # backend tests
cd frontend && npm run typecheck   # TypeScript strict typecheck
cd frontend && npm run build       # production build (includes typecheck)
```

Spec and tickets live in `.scratch/mindsforge/` — `spec.md` plus one issue file per ticket in `issues/`.
