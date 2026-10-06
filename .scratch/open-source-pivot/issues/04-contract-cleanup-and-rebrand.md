# 04: Contract cleanup, Minds removal, and health probe

**What to build:** The Minds service module is deleted along with alias/fingerprint machinery and `MINDS_BUILDER_API_KEY`/`MINDS_AGENT_ID` settings. The domain error type is renamed (`LLMError`), the health endpoint probes `GET {OPENAI_BASE_URL}/models` and reports `llm: unconfigured|ok|down`, and the sidebar drops "Powered by Minds / Animoca Brands" copy.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] No `minds` imports or `MINDS_*` env vars remain anywhere in backend code
- [ ] Health endpoint returns the renamed LLM status and frontend renders it
- [ ] Sidebar shows neutral backend copy
- [ ] Backend test suite is green without the old Minds module
