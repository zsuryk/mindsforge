# LLM integration is fail-closed

*Supersedes the previous version of this ADR ("Mind integration is fail-closed"). The Mind is no longer a vendor-hosted agent but any OpenAI-compatible endpoint, so the fail-closed contract is unchanged while the credential boundary moves from Minds keys to `OPENAI_BASE_URL`/`OPENAI_API_KEY` — a creator supplies their own, and a fully offline server (Ollama, LM Studio, vLLM) counts as configured.*

The Mind is not optional: a scoring failure fails the job, and a failure at experiment-conclusion time (when the Mind must pick the winner) fails the experiment — no skipping unscored clips, no fallback to highest-CTR. This keeps the Mind genuinely integral rather than decorational, at the cost of requiring a reachable LLM backend and clear error messages instead of degraded output. Running with an unconfigured or unreachable LLM was treated as the "working offline" mode originally; that mode is deliberately withdrawn for scored output.

**Considered Options:**
- Degrade to heuristic scoring when the endpoint is unreachable — jobs would always complete, but scores would silently mix model verdicts with guesses, which is the thing to avoid.
- Require an API key for every endpoint, including local servers — simpler configuration, but it breaks the offline-first promise of running Ollama without credentials.