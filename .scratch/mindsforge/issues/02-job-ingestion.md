# 02 — Job ingestion

**What to build:** End-to-end job intake. A user submits a processing job — either by pasting a source URL or uploading a media file — from the frontend jobs page. The request is accepted with 202, a job record persists in the database with status PENDING, and the job appears in the jobs list with a PENDING status badge. Job detail can be fetched by id and shows the same state.

**Blocked by:** 01 — Project skeleton

**Status:** ready-for-agent

- [x] Jobs table exists (SQLAlchemy model + table creation) with all fields from the spec
- [x] Creating a job persists it and returns job id + status; duplicate/submission errors are handled gracefully
- [x] Jobs page: submission form (URL or file upload), list of jobs, status badges, polling refresh of job state
- [x] Job detail endpoint returns the persisted record
- [x] A manually submitted job survives a backend restart (persisted, not in-memory)