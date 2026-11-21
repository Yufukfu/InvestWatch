# 0102. Scraper job queue and scheduler

- Status: proposed
- Date: 2026-11-21
- Deciders: (human, Adam's module; to be filled in)

Agent draft: Context, Options and evidence only. The decision and its rationale are for a human.

## Context

`scraper-v1` (`openspec/changes/scraper-v1/design.md`) needs to run collection per `sources.schedule_cron`, bound per-domain concurrency, retry transient failures and survive a restart. The stack already has PostgreSQL and Redis (`.docs/integration-plan.md` §1). The fetch path is `asyncio`-only (`iw-scraper-conventions`), so a sync-only worker would need a thread or process per job. Open source and on-premise only.

## Options considered

Evidence read from packages installed into a scratch venv (Python 3.9.6). Nothing was run against a live Redis or PostgreSQL, so runtime behaviour is **untested**.

1. **`arq` 0.28.0** (Redis)
   - Native `async` workers: `Worker` with `max_jobs` concurrency, per-function `timeout` and `max_tries`, a `Retry` exception, and `arq.cron.cron(...)` for cron jobs (`arq/cron.py`, `arq/worker.py`).
   - Needs Redis only (`redis[hiredis]<6`); `requires-python >=3.9`. The cron syntax is field-based (`hour`, `minute`, ...), not a cron string, so `sources.schedule_cron` would need translating.
2. **`procrastinate` 3.6.0** (PostgreSQL)
   - Async-first; periodic tasks in `periodic.py`, retry strategies in `retry.py`, own SQL schema (`schema.py`, `sql/`), worker and CLI. Uses `psycopg[pool]`, `croniter`, `attrs`; `requires-python >=3.9`.
   - Needs no Redis for the queue, and queued jobs share the transaction database; adds its own tables to PostgreSQL that Damian's module does not own.
3. **`APScheduler` 3.11.3** (scheduler only)
   - `AsyncIOScheduler` runs coroutines in the service's own event loop; no separate worker or broker. Persistent job stores need extras (`sqlalchemy`, `redis`). Retries and per-domain limits must be written by us. `requires-python >=3.8`.
4. **`rq` 2.8.0** (Redis)
   - Sync workers (no `async def` in its job code), with `CronScheduler`/`CronJob` in `cron.py`; async fetch code would have to be wrapped with `asyncio.run` per job. Needs `redis`, `croniter`; `requires-python >=3.9`.

Not looked at: Celery, Dramatiq, Temporal (heavier than the hackathon needs, by assumption, not evidence).

## Decision

(to be written by a human)

## Consequences

(to be written by a human)

Points a decider may want checked: whether the cron string in `sources` must be used as is, whether the dedup unique index and `job_errors` should live in the same transaction as the queue, and who owns extra PostgreSQL tables.
