# 05: Docs, env example, LICENSE, and dependency cleanup

**What to build:** `.env.example` documents the OpenAI-compatible settings with Ollama/LM Studio/OpenRouter examples and keeps Tavily/Whisper/ffmpeg keys. README prerequisites and config sections are rewritten for self-serve OSS setup ("contact for the Minds keys" removed). CONTEXT.md gloss updated. ADR-0002 retitled/superseded and ADR-0006 marked superseded. `@animocabrands/minds-cli` removed from frontend dependencies and the lockfile regenerated. MIT LICENSE added at repo root.

**Blocked by:** 04

**Status:** done (fd57d6f)

- [x] `cp .env.example .env` + documented values yields a working backend against a local OpenAI-compatible server
- [x] README setup steps verified start-to-finish without Minds credentials
- [x] `npm install` succeeds using only the public registry
- [x] LICENSE file present at root
