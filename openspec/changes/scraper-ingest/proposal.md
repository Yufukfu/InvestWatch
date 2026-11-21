# Proposal

## Why

`scraper-v1` produces a parsed page; analytics needs it as a schema-valid, deduplicated `documents` row with the raw HTML in MinIO and an `iw:documents` event. This change is the storage and announcement half of module A, split from the original `scraper-v1` so it can proceed in parallel and land when module C's migration is ready.

## What Changes

- Build the full `ScrapedDocument` from a parsed page and validate it against the contract schema.
- Deduplicate by `content_hash` (normalised text), insert into `documents`, store raw HTML in MinIO `iw-raw`, publish `{"document_id", "schema": "v1"}` to Redis Stream `iw:documents` only after the DB commit, and republish unpublished rows with a sweep.
- Persist job errors in `job_errors` (reasons from the closed set in `scraper-v1`'s `web-collection` spec).
- Out of scope: fetching and parsing (`scraper-v1`), the queue, scheduler, scan requests and events (`scraper-orchestration`), social collectors, Playwright, the REST API, analytics consumption.
- Owner: module A (`scraper/`).
- Contracts: writes `ScrapedDocument` v1 into `documents`, publishes the `iw:documents` message (integration points 1-3 in `.docs/integration-plan.md` §2). It changes none of those shapes. Needs from C (`migration-request.md`, ADR 0303): the Alembic migration (partial unique index, `committed_at` / `stream_published_at`, `job_errors`, `sources` columns for `scraper-orchestration`) and a compose file with postgres, redis and minio.
- Independent of `scraper-v1` code: the input is a plain dict shaped by the contract. Tests that need PostgreSQL, Redis or MinIO use a throwaway test schema until the real migration exists, and the end-to-end check against the migrated database runs in `scraper-orchestration`.

## Capabilities

### New Capabilities
- `document-ingest`: validate, deduplicate, store and announce a parsed document (DB, MinIO, Redis Stream).

### Modified Capabilities

## Impact

- New code under `scraper/` (ingest package) with pytest tests; dependencies `jsonschema`, a PostgreSQL driver, `redis`, `minio` (pinned, `pip-audit` before merge).
- Docs: `scraper/CLAUDE.md`, `.docs/STATUS.md`, `migration-request.md` handed to C.
