# Mind is the primary memory

The SQLite sidecar was a practical stopgap: it persisted brand rules, adaptation history, and experiment insights in a structured key/value store and injected them as text blocks into generation prompts. But this architecture duplicates what the Mind does natively — and for a hackathon organized by Minds, judges expect to see the Mind itself own and drive memory.

We shift the balance: the Mind's conversation thread becomes the authoritative memory. SQLite becomes a transparent backing store for UI features (Memory Inspector), not the intelligence layer. The Groq brand-rule extraction sidecar is removed entirely — the Mind natively captures and acknowledges creator preferences from its conversation context. Generation prompts (scoring, adaptation, experiment conclusion) are fed the Mind's own conversation thread as context, so every decision is grounded in what the Mind itself has seen and learned.

**Considered Options:**
- Keep SQLite sidecar as-is, surface memory in chat responses — minimal change, but doesn't showcase Minds' capability.
- Hybrid: SQLite for structured data, conversation thread for conversational context — more robust but more complex, harder to demo.

**Consequences:**
- Groq dependency is eliminated — fewer moving parts, simpler failure modes.
- Brand-rule extraction consistency depends on the Mind's reliability rather than a deterministic LLM call.
- The Memory Inspector retains SQLite as a read-only view for debugging; a new "Mind's View" section shows the conversation thread.
- A "Mind remembers" badge on clips/adaptations demonstrates persistence to judges.
