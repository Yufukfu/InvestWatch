# Proposal

## Why

Analytics (module C) has nothing to analyse until the scraper turns registered sources into schema-valid `ScrapedDocument` rows. This is the first vertical slice of module A and the prerequisite for the end-to-end demo and the hand-in.

## What Changes

- Add a scheduled collection job that reads active rows from `sources`, fetches each web page over the fetch ladder (see `iw-scraper-conventions`) and parses it into a `ScrapedDocument` (`platform: web`).
- Add an ingest step that validates the document against the contract schema, stores raw HTML in MinIO (`iw-raw`), inserts into `documents` deduplicated by `content_hash`, then publishes `{"document_id", "schema": "v1"}` to Redis Stream `iw:documents` after the DB commit.
- Record every block, timeout or parse failure as a job error with a reason; a failed fetch never produces a document with empty `text`.
- Pages that need `blocks` and screenshots (Playwright) are only flagged for later; rendering is not built here.
- Out of scope: social-media collectors (first platform needs its own ADR and change), Playwright rendering with `blocks`/screenshots, proxy pool management beyond reading `PROXY_LIST`, the `sources` editing UI (B), the REST API (C), and analytics consumption.
- Owner: module A (`scraper/`).
- Contracts: reads and writes `ScrapedDocument` v1 and the `sources` table, publishes the `iw:documents` event (integration points 1-3 in `.docs/integration-plan.md` §2). It changes none of them and needs no version bump.
- Assumptions: contract v1 is confirmed by A and B; `docker-compose.yml` with postgres, redis and minio exists (owned by C); the fetch client and queue choices are settled in ADRs drafted by this change before the matching tasks start.

## Capabilities

### New Capabilities
- `web-collection`: fetch a registered web source, detect blocks and failures, and parse the page into contract-shaped fields.
- `document-ingest`: validate, deduplicate, store and announce a parsed document (DB, MinIO, Redis Stream).

### Modified Capabilities

## Impact

- New code under `scraper/` (Python, async) with pytest tests and saved HTML fixtures in `scraper/tests/fixtures/`.
- Dependencies: a TLS-impersonating HTTP client, an HTML parser, a Postgres driver, `redis`, `minio`, `jsonschema` (all pinned, `pip-audit` before merge).
- Docs: `scraper/CLAUDE.md`, `.docs/STATUS.md`, ADR drafts in `.docs/decisions/`.
