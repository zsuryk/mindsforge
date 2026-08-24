# 04 — Remove Groq dependency from project config

**What to build:** The `groq` package and `GROQ_API_KEY` config are removed from the project, completing the cleanup.

**Blocked by:** 02 — Remove Groq brand-rule extraction sidecar

**Status:** done

- [x] Remove `GROQ_API_KEY` from `config.py`
- [x] Remove `groq` from `pyproject.toml` dependencies
- [x] Verify no remaining references to Groq in the codebase (grep for `groq`, `GROQ`, `Groq`)
