# MindsForge

AI-driven creator platform: automatically identifies high-converting short clips from long-form video/audio, creates platform-specific content variants, executes autonomous A/B testing, and manages persistent creator memory via Minds by Animoca Brands.

## Prerequisites

- Python 3.11+
- Node.js 20+
- System FFmpeg 6.0+ (media pipeline)

## Backend (FastAPI)

```sh
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in MINDS_BUILDER_API_KEY / MINDS_AGENT_ID / GROQ_API_KEY
.venv/bin/python -m app
```

Serves `http://localhost:8000` — health check at `/api/v1/health`.

## Frontend (Next.js 14)

```sh
cd frontend
npm install
cp .env.example .env
npm run dev
```

Serves `http://localhost:3000`. The header shows a live backend status light fed from `/api/v1/health`; the API base is `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`).

## Tests / typecheck

```sh
cd backend && .venv/bin/python -m pytest
cd frontend && npm run build   # includes TypeScript strict typecheck
```

## Spec and tickets

Live in `.scratch/mindsforge/` — `spec.md` plus one issue file per ticket in `issues/`.