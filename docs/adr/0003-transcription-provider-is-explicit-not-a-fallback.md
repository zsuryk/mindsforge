# Transcription provider is local Whisper

Transcription runs through a local faster-whisper model (`local`), selected via `TRANSCRIPTION_PROVIDER`. The provider runs faster-whisper (CTranslate2, CPU `int8`, `small` model by default) rather than openai-whisper (PyTorch-heavy) or whisper.cpp (needs a compiled binary), loading the model lazily and caching it per process. First use downloads the model to the Hugging Face cache; after that it runs fully offline. Failure semantics are fail-closed — a missing model or failed transcription fails the job with a descriptive message.

Note: A Groq-hosted Whisper provider was previously available but was removed in the mind-native-memory feature (ticket 04) to eliminate external dependencies and simplify the system.
