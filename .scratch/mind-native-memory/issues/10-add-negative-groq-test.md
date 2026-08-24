# 10 — Add negative Groq test for chat send

**What to build:** A test confirms that `send_chat_message()` never invokes the Groq sidecar, ensuring the brand-rule extraction was fully removed and can't regress.

**Blocked by:** 02 — Remove Groq brand-rule extraction sidecar

**Status:** done

- [x] Add a test in `test_chat.py` that mocks a Groq client (or mocks `rules.extract_and_persist_brand_rules`) and asserts it is never called when `send_chat_message()` is invoked
- [x] The test should call the `POST /api/v1/chat/messages` endpoint and verify the response has no `rules` field (or that the field is absent/empty)
- [x] Run the full test suite to verify no regressions
