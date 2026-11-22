# Proposal

## Why

Module 1 of the brief asks for a periodic update mechanism. Re-scans already run, but a re-scan that finds new text stores a new `documents` row (new `content_hash`, new id), so the old finding stays as if nothing happened, and an ad that is gone (404/410) after being flagged looks the same as a live one (issue #71, open item in `.docs/status/platform.md`).

## What Changes

- `GET /api/findings/{id}` derives the re-scan state of the finding's document on read and serves it as `document.scrape_meta.rescan`: `{state: "current" | "changed" | "removed", latest_document_id, checked_at}`.
  - `changed`: a later fetch of the same page (same `source_id`, same `canonical_url` or else `url`) has a different `content_hash`; the old finding is superseded by that document's finding.
  - `removed`: the latest later fetch has `http_status` 404 or 410, or a `job_errors` row for the page (`reason = http_error`, `detail` `HTTP 404`/`HTTP 410`) is newer than the last fetch.
- Nothing is stored and no table changes: the state comes from existing `documents` and `job_errors` columns.

No contract change: `finding.schema.json` is closed (`additionalProperties: false`), so the state cannot go on the finding itself; `scrape_meta` in `scraped-document.schema.json` is the one open object (`additionalProperties: true`). A badge on the findings list would need an optional `Finding` field (proposed `rescan_state`), a contract change for the team; recorded in `follow-ups.md`.

Module: `api/` (Damian). Consumers: `web/` (Kacper) reads the new key for the badge and the detail line.

## Capabilities

### New Capabilities

### Modified Capabilities

- `rest-api`: the finding detail carries the derived re-scan state.
