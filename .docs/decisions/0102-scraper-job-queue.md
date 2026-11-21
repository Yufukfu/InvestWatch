# 0102. Scraper job queue and scheduler

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the human via the PR that merges `scraper-v1`

## Context

`scraper-v1` (`openspec/changes/archive/2026-11-21-scraper-v1/design.md`) needs to run collection per `sources.schedule_cron`, bound per-domain concurrency, retry transient failures and survive a restart. The stack already has PostgreSQL and Redis (`.docs/integration-plan.md` §1). The fetch path is `asyncio`-only (`iw-scraper-conventions`), so a sync-only worker would need a thread or process per job. Open source and on-premise only.

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

Use **`arq`** (Redis) with a thin scheduler that enqueues a job per active source from `schedule_cron`.

Rationale, from the evidence above: it is a native `async` queue with per-function `timeout`, `max_tries` and `Retry` (`procrastinate` is also async-first; `APScheduler` has no queue; `rq` is sync-only), it needs Redis only, which the stack already has, and it adds no tables to a PostgreSQL schema that Damian's module owns (unlike `procrastinate`). In-house evidence (`hen68/cheaply-self-hosted`, `shared/ratelimit.py`) gives a Redis token-bucket limiter with a local fallback to port for per-domain limits; neither in-house repo uses a queue library.

## Consequences

- `arq` cron is field-based, so `schedule_cron` strings are parsed by us; an invalid expression is a recorded `invalid_request`, not a crash. Each due job gets a unique id per source and cron slot so replicas do not double-enqueue; that relies on `arq` rejecting a duplicate job id. Verified with `arq` 0.28.0 on Redis 7 (`scraper-orchestration` 2.4): a second `enqueue_job` with the id of a queued job returns `None`, and the scheduler test enqueues one job for two concurrent schedulers.
- The evidence shows `max_jobs` per worker and no per-domain limit, so per-domain control is ours and lives in Redis: a counting semaphore for jobs running at once and a token bucket for request starts, not in-process state.
- Resume after a restart is verified against Redis 7 (`scraper-orchestration` 1.2): jobs queued when a worker is killed with SIGKILL stay in Redis and run on the next worker without being enqueued again, so this ADR stands. A job that was running at the kill stays `in_progress` until arq's in-progress key expires (job timeout plus 10 s); recovering it sooner is tracked in `openspec/changes/scraper-orchestration/follow-ups.md`.
- Ownership of cross-job domain state (checked against `scraper-v1` PR #19, 2026-11-21): the queue wrapper is the single owner of the per-domain concurrency cap, the `Retry-After` deferral and the failure pause (`guards.py`, keys `iw:sem:*` and `iw:domain:*`). Only the queue sees a job's final outcome after its retries, and a collector reports one attempt (`iw-scraper-conventions`), so the failure count cannot live in the fetch path without counting every retried attempt. The collector passes the raw `Retry-After` of a failed fetch on in `AttemptResult`. The `DomainGate` class in `scraper-v1` (`domaingate.py`, keys `iw:dom:*`) is called by no collector yet and would duplicate this state under other keys, so it should not be wired in; the request-start rate limiter (`ratelimit.py`) stays in the fetch layer, where each request is made.
