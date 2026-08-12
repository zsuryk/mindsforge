# MindsForge

AI-driven creator platform that repurposes long-form content into platform-adapted short clips, A/B tests them autonomously, and grows a persistent creator memory inside a Minds agent.

## Language

**Mind**:
The creator's Minds agent. It owns the persistent memory and authors everything generated — virality scores, hooks, titles, platform features, and learned insights. It never cuts, renders, or publishes media; code does that.
_Avoid_: agent, model, brain

**Memory**:
The Mind's persistent context tree, organized under keys such as `brand_voice`, `historical_insights`, `ab_test_history`, and `adaptation_history`.

**Job**:
A submitted long-form source (URL or upload) being processed by the ingestion pipeline.
_Avoid_: video, upload

**Clip**:
A short-form segment cut from a job's source, with transcript text and a virality score.
_Avoid_: highlight, cut

**Platform**:
The destination channel content is adapted for (YouTube, TikTok, or X).
_Avoid_: channel, network

**Surface**:
A content form within a platform (YouTube: Shorts or long-form video; TikTok: feed video; X: post). Adaptations target a platform-surface pair.
_Avoid_: format (overloaded), type

**Adaptation**:
The packaged result of repurposing one clip for one platform-surface: a feature manifest plus downloadable assets, generated on demand by the Mind. The creator publishes the assets manually — MindsForge never publishes.
_Avoid_: package, remix, repurpose-run, post

**Feature**:
A platform-specific content element an adaptation carries (chapters, tags, polls, quizzes, Test & Compare, shorts link, captions, overlays, stickers, pinned comments).
_Avoid_: element, metadata

**Asset**:
A downloadable file an adaptation produces (thumbnail variants, SRT caption file, chapter list).
_Avoid_: artifact, output-file

**Test & Compare**:
YouTube's built-in A/B mechanism for titles and thumbnails; in MindsForge it is realized by running the three thumbnail variants of an adaptation through the experiment engine.
_Avoid_: thumbnail test

**Experiment**:
A multi-variant A/B test on a clip for a platform. When it concludes, the Mind decides the winning variant and authors the learned insight.
_Avoid_: A/B test, trial

**Learned insight**:
The natural-language conclusion of an experiment, authored by the Mind and persisted to its memory.
_Avoid_: lesson, takeaway