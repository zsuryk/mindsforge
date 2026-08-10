# 01 — Project skeleton

**What to build:** The bare running system both halves live in. The backend boots a FastAPI app with config loaded from the backend env file, CORS open to the frontend origin, and a health endpoint; the frontend boots a Next.js 14 App Router app with a dark (`bg-slate-950`) layout shell and sidebar navigation, and renders a live system-status indicator fed by the backend health endpoint. A developer can run both processes locally, open the UI, and see the backend is up.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] Backend app entry point loads all env vars via settings, applies CORS middleware, mounts routers, and exposes a health/status route
- [x] Frontend project initialised with TypeScript strict mode, Tailwind, and the app shell + sidebar navigation
- [x] Frontend renders backend health status fetched through the configured API URL
- [x] Both `.env` files exist with all keys from the spec and are git-ignored
- [x] `requirements.txt` and `package.json` pin the spec'd dependencies