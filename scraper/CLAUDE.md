# scraper (module A)

Collects web and social-media content and writes `ScrapedDocument` rows (contract v1, `.docs/integration-plan.md` §3) plus HTML and screenshots to MinIO. Downstream, `analytics` consumes the Redis Stream `iw:documents`; the scraper knows nothing about analytics.

Run `iw-scraper-conventions` before writing any fetch or parse code. Team decision: start with **one** social platform, add more only if time allows.

## Stack

- Python, async-first. Fetch with a **TLS-impersonating client** (noble-tls or similar; chosen via ADR after reading the real API) so requests look like a browser. Playwright only as a fallback and for sources that need `blocks`/`screenshots`.
- Job queue and schedule: `arq` on Redis ([ADR 0102](../.docs/decisions/0102-scraper-job-queue.md)). Storage: PostgreSQL + MinIO + Redis from compose.
- Tests: pytest, saved real responses in `tests/fixtures/`, no live network in unit tests.

## Done means

Schema-valid documents land in `documents`, an `XADD iw:documents` follows, a rerun dedups by `content_hash`, and a block or parse failure is logged as a job error instead of an empty document.

## Orchestration (`scraper-orchestration`)

Spec and design: `openspec/changes/scraper-orchestration/` (`specs/scan-orchestration/spec.md`, `design.md`, `follow-ups.md`).

| Module in `src/iw_scraper/` | Owns |
|---|---|
| `jobs.py` | one job: run lock, per-domain cap, retry and deferral, `scan.*` events, status; `QueueSettings` |
| `guards.py`, `retry.py` | Redis lock, lease semaphore, domain cooldown; backoff and `Retry-After` |
| `scan_requests.py`, `scheduler.py` | `iw:scan-requests` consumer; cron planner and sweep |
| `worker.py`, `supervise.py` | supervised worker and consumer, graceful stop, reconnect with backoff |
| `health.py`, `logs.py`, `events.py`, `sources.py` | `GET /health`, JSON logs, `iw:events` envelope, `SourceStore` protocol |

- The collector and ingest plug in through `ctx["run_source"]` and `ctx["sources"]`; see `iw-scraper-conventions` for what a collector must and must not do. Do not edit `types.py` without telling the owner.
- Tests need a real Redis: `COMPOSE_PROJECT_NAME=iw-scraper-orch docker compose -f scraper/compose.test.yaml run --rm --build test` from the repository root. Settings are `SCRAPER_<FIELD>` variables, listed in `.env.example`.

