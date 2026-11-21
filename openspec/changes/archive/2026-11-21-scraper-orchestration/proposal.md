# Proposal

## Why

With fetching and parsing (`scraper-v1`) and ingest (`scraper-ingest`) in place, the scraper still needs to run them: queued jobs, a schedule, scan requests from the dashboard, progress events, and behaviour that stays correct with several workers. This is the third and last slice of module A, split from the original `scraper-v1`.

## What Changes

- A job queue (`arq`, ADR 0102) runs every collection with a per-domain concurrency cap, retries owned by the queue, resume after restart and a per-source run lock held for the whole job.
- A run that reports a deferral (`Retry-After`, paused domain, all proxies cooling) is requeued with a delay, not failed; the queue records one outcome per job into the domain failure cooldown.
- Scan requests from Redis Stream `iw:scan-requests` enqueue jobs; `scan.started` / `scan.finished` are published on `iw:events` once per job; `sources.last_run_at` and `last_run_status` are written (the API counts `documents` rows on read, so there is no `documents_count` column).
- A scheduler enqueues each due job exactly once across workers from `schedule_cron` (`null` = manual only) and runs the republish sweep on an interval.
- Workers are stateless and stop gracefully; jobs have a timeout; Redis and PostgreSQL reconnect with backoff; `GET /health`; JSON logs on stdout.
- First real end-to-end test on the KNF page (served by a local stub), including two workers and an opt-in live smoke test with a seed script.
- Out of scope: social-media collectors (`scraper-v2`), Playwright rendering (`scraper-v3`), crawling beyond one URL per run, the REST API, analytics consumption.
- Owner: module A (`scraper/`).
- Depends on: `scraper-v1` (fetch, parse, guards) and `scraper-ingest` (storage, publish, `job_errors`) merged, and on C's migration and compose file (`scraper-ingest` task 1.1). Starts from a branch stacked on those.
- Contracts: consumes the `scan_request` message from `iw:scan-requests`, publishes `scan.started`/`scan.finished` events on `iw:events` and writes `sources.last_run_at` and `last_run_status` only. It changes none of those shapes.

## Capabilities

### New Capabilities
- `scan-orchestration`: job queue, run lock, schedule, scan requests and progress events, scale-out, stability, health and logs.

### Modified Capabilities

## Impact

- New code under `scraper/` (queue, scheduler, consumer, health) with pytest tests; dependencies `arq`, `croniter` and `redis` (pinned, `pip-audit` before merge); `/health` is a small asyncio server with no dependency.
- Docs: `scraper/CLAUDE.md`, `.docs/STATUS.md`, `iw-scraper-conventions`, `.env.example` entries.
