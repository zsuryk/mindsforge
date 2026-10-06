# 06: Test suite port to the new client

**What to build:** `test_minds.py` is reworked into tests for the new LLM client, mocking at the httpx HTTP layer (`MockTransport`) against an OpenAI-shaped API — covering the two-step flow, fence-tolerant JSON extraction, unknown-variant and empty-reasoning rejection, and error mapping. Other backend tests are updated to import the new module/names. Migration test for `chat_messages` included. No `minds` references remain in tests.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Full backend suite passes (`uv run pytest`) with zero Minds-API mocks
- [ ] Grep for `hellominds|MINDS_|minds\.py` in tests returns nothing
- [ ] Frontend `vitest` suite passes with sidebar copy change covered
