# Proposal

## Why

Analytics (module C) has nothing to analyse until the scraper turns registered sources into schema-valid `ScrapedDocument` rows. This is the first vertical slice of module A: a scalable, stable scraping engine proven end to end on one easy real site, so later sites are added by a parser module and a `sources` row, not by engine changes.

## What Changes

- First target: the KNF public warnings page (`https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`), a server-rendered public page whose `robots.txt` allows all (checked 2026-11-21 with plain GETs). It is the regulator's own list of unauthorised entities (module M3 material). Seed row: `platform = web`, `source_kind = unknown`, `target_modules = ["M3"]`, daily cron. One URL per source run in v1.
- A job queue (`arq`, ADR 0102) runs every collection with bounded per-domain concurrency, retries owned by the queue, resume after restart, a per-source run lock and a scheduler driven by `schedule_cron` (`null` = manual only). All shared state lives in Redis or PostgreSQL, so workers scale with a replica count.
- A fetch layer over a TLS-impersonating client (ADR 0101) with a fresh session per run, headers sent in the browser profile's order, a different proxy for each request (`PROXY_ROTATION`, default `per_request`), a Redis-shared per-domain rate limit, `Retry-After` deferral and a per-domain failure cooldown.
- A parser registry keyed by host (generic parser by default) that produces contract fields.
- An ingest step: validate against the contract schema, dedup by `content_hash`, store raw HTML in MinIO (`iw-raw`), insert into `documents`, publish `{"document_id", "schema": "v1"}` to Redis Stream `iw:documents` only after the DB commit, with a republish sweep.
- Every block, timeout or parse failure is a typed job error; a failed fetch never produces an empty document.
- Scan requests from `iw:scan-requests` enqueue jobs; `scan.started` / `scan.finished` are published on `iw:events` once per job; `sources.last_run_at`, `last_run_status` and `documents_count` are written.
- `GET /health`, JSON logs on stdout, graceful SIGTERM, job timeouts and reconnect with backoff.
- Out of scope: social-media collectors, Playwright rendering with `blocks`/screenshots, following links or crawling beyond one URL per run, proxy pool health management beyond skipping failing proxies, the `sources` editing UI (B), the REST API (C), analytics consumption, extraction of `published_at` and `author` (both stay null, which the contract allows).
- Follow-up changes: the challenge requires social-media collectors with UA and proxy rotation and rendered `blocks`/screenshots for the M2 visual rules (R4-R8, R13). They are planned as `scraper-v2` (first social platform, per ADR 0103) and `scraper-v3` (Playwright rendering), not part of this change.
- Owner: module A (`scraper/`).
- Contracts: reads and writes `ScrapedDocument` v1 and the `sources` table (including `last_run_*` and `documents_count`), publishes the `iw:documents` event (integration points 1-3 in `.docs/integration-plan.md` §2), consumes the `scan_request` message from `iw:scan-requests` and publishes `scan.started`/`scan.finished` on `iw:events`. It changes none of those shapes. Open with C: the `scrape_meta.scraper` value for a TLS-impersonating client (not required by the schema, so it blocks nothing; a v1 enum addition would be a contract change), and the shared migration (§7: migrations live in `api`) for the unique index `(source_id, content_hash)`, `job_errors` (nullable `source_id`, no foreign key), the published marker with its commit time, the `sources` columns `last_run_status` and `documents_count`, and `docker-compose.yml` with postgres, redis and minio. Note for C: `.docs/integration-plan.md` §6 and §3 are stale against `events.schema.json` (scan `status`) and `source.schema.json` (`last_run_status`, `documents_count`).
- Assumptions: contract v1 is confirmed by A and B; ADR 0101 and 0102 are written by this change before the matching tasks start.

## Capabilities

### New Capabilities
- `web-collection`: fetch a registered web source with a fresh session, ordered headers and per-request proxies, detect blocks and failures, and parse the page into contract-shaped fields.
- `document-ingest`: validate, deduplicate, store and announce a parsed document (DB, MinIO, Redis Stream).
- `scan-orchestration`: job queue, run lock, schedule, scan requests and progress events, scale-out, stability, health and logs.

### Modified Capabilities

## Impact

- New code under `scraper/` (Python 3.12, async) with pytest tests and saved real HTML fixtures (the KNF page among them) in `scraper/tests/fixtures/`.
- Dependencies: a TLS-impersonating HTTP client, an HTML parser, `arq`, a Postgres driver, `redis`, `minio`, `jsonschema` (all pinned, `pip-audit` before merge).
- Docs: `scraper/CLAUDE.md`, `.docs/STATUS.md`, `iw-scraper-conventions` (proxy now per request, session per run), ADRs 0101 and 0102 in `.docs/decisions/`.
