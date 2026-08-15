# MindsForge

**Turn long-form videos into high-converting short clips — automatically.**

MindsForge is an AI-powered creator platform that:

- **Finds the golden moments** — scans long-form video/audio and identifies the most viral-worthy short clips.
- **Adapts for every platform** — generates platform-specific variants of each clip.
- **A/B tests by itself** — launches experiments and tracks which variant wins.
- **Remembers creators** — persistent creator memory via Minds by Animoca Brands.

## What it generates

Every clip is packaged into a downloadable, platform-ready content kit:

| Surface | Rendered thumbnails | Copy & hooks | Chapters & captions | Extras | A/B testing |
|---|---|---|---|---|---|
| **YouTube Shorts** | 3× 1080×1920 PNGs | Platform hooks | — | — | Test & Compare on thumbnails |
| **YouTube Long-form** | 3× 1280×720 PNGs | Tags | `chapters.txt` + SRT | Poll, quiz, Shorts link | Test & Compare on thumbnails |
| **TikTok** | Per-segment overlay renders | Caption style | SRT auto-captions | Stickers, pinned comment | — |
| **X** | — | Caption + hashtags | — | — | — |

Everything renders into real assets (thumbnail PNGs, `captions.srt`, `chapters.txt`) with a per-surface publish checklist in the studio — and every generated package is appended to the creator's persistent memory, so each new generation compounds on past learnings.

## Prerequisites

- **uv** — Python package manager
- **Node.js 20+** (LTS recommended)
- **FFmpeg 6+** (in system PATH)
- **Three API keys** — jobs are fail-closed without them: `GROQ_API_KEY` (transcription), `MINDS_BUILDER_API_KEY` + `MINDS_AGENT_ID` (scoring/memory). Grab a free Groq key at https://console.groq.com; contact for the Minds keys or generate one.
- You may need to use a VPN if you are located in a region unsupported by Groq.

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

Fill in the three keys in `.env`. Everything else has sane defaults.

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
4. Explore the rest: **Clips** (per-clip virality), **A/B Experiments** (launch a test between variants — the platform picks the winner), and **Memory Inspector** (what MindsForge remembers about the creator).

## Troubleshooting

| Problem | Fix |
|---|---|
| Job fails with `Minds is not configured` or `GROQ_API_KEY is not configured` | Keys missing from `backend/.env`, or the backend wasn't restarted after adding them (Ctrl+C, then `uv run --module app`). |
| `command not found: ffmpeg` / jobs fail with an ffmpeg error | FFmpeg not on PATH — install it per OS and open a new terminal. |
| Port 8000 already in use | Quit the other process, or run with `PORT=8001` and point the frontend's `NEXT_PUBLIC_API_URL` at it. |
| Video fails to download | Some hosts (e.g. YouTube) block automated downloads — use a direct `.mp4` URL instead. |
| Red status light in the header | Backend isn't running — start it (see **Run**). |
| Groq transcription failed: Error code: 403 | Region unsupported by Groq — use a VPN |

---

## For contributors

```sh
cd backend && uv run pytest        # backend tests
cd frontend && npm run typecheck   # TypeScript strict typecheck
cd frontend && npm run build       # production build (includes typecheck)
```

Spec and tickets live in `.scratch/mindsforge/` — `spec.md` plus one issue file per ticket in `issues/`.
