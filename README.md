# MindsForge

**Turn long-form videos into high-converting short clips — automatically.**

MindsForge is an AI-powered creator platform that:

- **Finds the golden moments** — scans long-form video/audio and identifies the most viral-worthy short clips.
- **Adapts for every platform** — generates platform-specific variants of each clip.
- **A/B tests by itself** — launches experiments and tracks which variant wins.
- **Chats with the creator** — ask it anything, state brand rules ("always use bold captions"), and it researches live trends (Tavily) before answering.
- **Remembers creators** — persistent creator memory in local SQLite, proven at a glance on the dashboard.
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
- **An OpenAI-compatible LLM endpoint** — the Mind is the model you point MindsForge at, so any chat-completions API works: OpenAI, Ollama, LM Studio, vLLM, OpenRouter. Configure it with `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in `backend/.env` (see **Configure**). Scoring, experiment verdicts, adaptations, and chat are all fail-closed: without a working endpoint, those units fail with a message naming the setting to fix.
- **Optional keys** — transcription runs locally with Whisper by default (first run downloads the model, then offline). Chat trend research needs `TAVILY_API_KEY` (free key at https://tavily.com).

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

Point the backend at your endpoint. Every provider uses the same four settings:

| Setting | What it is |
|---|---|
| `OPENAI_BASE_URL` | Base URL of the chat-completions API (default `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Model id sent on every request — one model for all flows (default `gpt-4o-mini`) |
| `OPENAI_API_KEY` | Key for endpoints that authenticate; leave empty for local servers that ignore it (Ollama, LM Studio, vLLM) |
| `OPENAI_TIMEOUT_SECONDS` | Per-request timeout in seconds (default `120`) |

Ready-made setups (each is a commented example in `.env.example`):

| Provider | `OPENAI_BASE_URL` | `OPENAI_MODEL` | `OPENAI_API_KEY` |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | your OpenAI key |
| Ollama (fully offline) | `http://localhost:11434/v1` | e.g. `llama3.1` | empty |
| LM Studio (fully offline) | `http://localhost:1234/v1` | the model id in LM Studio's server log | empty |
| OpenRouter | `https://openrouter.ai/api/v1` | e.g. `anthropic/claude-sonnet-4.5` | your OpenRouter key |

For Ollama, pull the model once so it is available offline:

```sh
ollama pull llama3.1
```

Add `TAVILY_API_KEY` too if you want trend research from chat. Everything else has sane defaults. Confirm the wiring with `curl http://localhost:8000/api/v1/health` after starting the backend — the `llm` field reads `ok` when the endpoint answers, `unconfigured` when `OPENAI_BASE_URL`/`OPENAI_API_KEY` are missing, and `down` when it is configured but unreachable.

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

The Mind's memory survives backend restarts — it lives in local SQLite, which is the source of truth for brand rules, learned insights, adaptation history, and the chat thread. This scripted walkthrough proves it end to end.

**Day 1 — build the memory (~3 min)**

1. Open **Chat** and tell the Mind a brand rule, e.g. *"always use bold captions and never clickbait"* — the reply chip confirms *"Your Mind saved: …"*.
2. Give the Mind a voice to remember: open **Memory Inspector** and write the `brand_voice` key with your style, e.g. `Bold, direct, and generous with practical value.`
3. Ask it to research a trend: *"search trends for hook retention 2026"* (needs `TAVILY_API_KEY`). The results land in the chat as a system note.
4. Open a clip in the **Clips** studio and generate a YouTube Shorts adaptation — the features are written to `adaptation_history`.
5. Launch an **A/B test** on the clip; once the view threshold is reached the Mind picks the winner and writes the insight to memory.
6. Check the dashboard: the **Mind at Work** feed shows rule saves, trend research, and adaptations live; the **What your Mind remembers** card shows the brand voice, rules, insights, and trend queries with ages.

**Day 2 — prove it persisted (~2 min)**

1. Restart the backend (Ctrl+C, then `uv run --module app`). SQLite and the chat thread survive.
2. Ask the chat *"what's my brand voice?"* and *"what did my experiments teach me?"* — the Mind answers from the stored memory and thread.
3. Generate a new adaptation and watch it follow your saved rule — the rule is fed into the generation prompt.
4. Open **Memory Inspector** — the full accumulated history (rules, trends, insights, adaptations) is all there.

## Troubleshooting

| Problem | Fix |
|---|---|
| Job fails with `The LLM backend is not configured` | `OPENAI_BASE_URL`/`OPENAI_API_KEY` are missing from `backend/.env` (or the backend wasn't restarted after adding them — Ctrl+C, then `uv run --module app`). |
| Health endpoint reports `"llm": "unconfigured"` or `"llm": "down"` | `unconfigured` means the LLM settings are missing; `down` means they are set but `GET {OPENAI_BASE_URL}/models` doesn't answer — check the base URL, that the local server is running, and that the model id exists. |
| Calls fail with `LLM request failed with status 401` | The endpoint requires auth and the key is wrong or empty — set `OPENAI_API_KEY` (only OpenAI/OpenRouter-style endpoints need one). |
| Calls fail with `LLM request failed with status 404` | `OPENAI_BASE_URL` must include the API version path (`https://api.openai.com/v1`, `http://localhost:11434/v1`, …) and `OPENAI_MODEL` must be a model the endpoint serves. |
| Trend research fails with `TAVILY_API_KEY is not configured` | Add `TAVILY_API_KEY` to `backend/.env` and restart the backend — trend research is fail-closed without it. |
| `command not found: ffmpeg` / jobs fail with an ffmpeg error | FFmpeg not on PATH — install it per OS and open a new terminal. |
| Port 8000 already in use | Quit the other process, or run with `PORT=8001` and point the frontend's `NEXT_PUBLIC_API_URL` at it. |
| Video fails to download | Some hosts (e.g. YouTube) block automated downloads — use a direct `.mp4` URL instead. |
| Red status light in the header | Backend isn't running — start it (see **Run**). |

---

## For contributors

```sh
cd backend && uv run pytest        # backend tests
cd frontend && npm run typecheck   # TypeScript strict typecheck
cd frontend && npm run build       # production build (includes typecheck)
```

Spec and tickets live in `.scratch/open-source-pivot/` — `spec.md` plus one issue file per ticket in `issues/`.

## License

MIT — see [LICENSE](LICENSE).
