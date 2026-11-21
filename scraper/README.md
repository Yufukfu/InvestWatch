# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** A
- **Status:** queue, scan requests, scheduler, events, health and graceful shutdown are built (`openspec/changes/scraper-orchestration/`); the collector and ingest are separate changes. The service entry commands arrive with them.
- **Queue:** `arq` on Redis ([ADR 0102](../.docs/decisions/0102-scraper-job-queue.md)). A job holds a per-source run lock, respects a per-domain concurrency cap, retries timeouts and HTTP 5xx with backoff, and reports `scan.started` / `scan.finished` on Redis `iw:events`.

## Run the tests

Needs Docker (the tests use a real Redis). From the repository root:

```bash
COMPOSE_PROJECT_NAME=iw-scraper-orch docker compose -f scraper/compose.test.yaml run --rm --build test
```

## Configuration

Environment variables only; see [`.env.example`](.env.example). `REDIS_URL` is required, everything else has a default.
