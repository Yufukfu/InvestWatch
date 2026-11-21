# Follow-ups

Findings of the `iw-reviewer` passes on group 1 (`bdeb218..77cb671`) and group 2 (`26a3cf1..bd6be4c`) and their declined-to-judge lists. Fixed findings are in the follow-up commit and not repeated here.

| Item | Disposition | Note |
|---|---|---|
| `run_source` raising leaves no job error and no domain outcome (the lock is released, arq logs the failure) | docs | Contract documented in `jobs.py`: collectors report failures as an `AttemptResult`. No `Reason` fits an internal error; revisit in task 2.1 when the real run is wired. |
| A job that was mid-run when its worker was killed stays in progress until arq's in-progress key expires (about the job timeout plus 10 s) | fix-here | Task 3.1: shorter in-progress TTL or arq `health_check`; the spec scenario covers queued jobs only. |
| arq's own job timeout (`attempt_timeout` plus slack) is untested; only the inner `asyncio.timeout` is | wont-fix | The inner timeout fires first and 3.1 tests its lock and slot release; the outer one is a backstop. |
| `iw:domain:*:failures` has no expiry, so "consecutive" has no time bound | wont-fix | The spec sets no time bound; a failure streak ends on the first success. |
| `iw:sem:*` keys are never deleted | wont-fix | One small key per domain, cosmetic. |
| Awaiting the cancelled lease keeper cannot be observed by a test | wont-fix | An in-flight renewal lands server-side either way; the await only guarantees the task has stopped. |
| `pip-audit` for `arq==0.28.0` and `redis` | docs | Run in closing task 4.2 before merge (hard rule). |
| Per-domain request-start rate limit (token bucket) and its Redis-down fallback | new-item | Not built here; design.md no longer claims it. It belongs to the fetch layer in `scraper-v1`, which owns the "per-domain rate limit" politeness rule. The concurrency cap is built (2.2). |
| `documents` of `scan.finished` and `sources.documents_count` count the final attempt only; rows inserted by an attempt that then failed transiently are not added | docs | Decision: a collector inserts rows when it succeeds, so a retried attempt has none to lose; revisit with the real ingest (2.1) if a partial attempt can insert. |
| An outer arq timeout (not a shutdown) cancels `execute_job`: the lock is kept up to `attempt_timeout` and a started job gets no `scan.finished` | docs | Shutdown cancels are requeued and finish later; the backstop timeout is rare, since the inner timeout fires first. Revisit if a collector can hang outside `run_source`. |
| A scan request redelivered after its job's arq result key expired (about 1 h) runs again | wont-fix | Needs a pending message older than the result retention; the claim idle time is far shorter. |
| `iw:cron-invalid:*` and `iw:started:*` keys: the first has no expiry | wont-fix | One small key per bad source, removed when the cron is fixed. |
| The `python -m iw_scraper worker` and `scheduler` commands (composition root: source store, collector, ingest, health checks for PostgreSQL and MinIO, SIGTERM handler setting `stop`) | fix-here | `run_worker`, `run_consumer`, `Scheduler.run` and `serve_health` exist and are tested; the commands are wired in 2.1/3.3 when the real collector, ingest and PostgreSQL store land. |
| `mark_running` / `mark_finished` idempotency in the PostgreSQL `SourceStore` | docs | Task 2.1 implements the store; `execute_job` calls each once per job. |
| `requested_at` is not validated and stale requests are not dropped | wont-fix | The spec asks only for a valid `source_id`. |
| `croniter` accepts a 6-field (seconds) expression; `schedule_cron` is a 5-field cron per the contract | wont-fix | Evaluated per minute, so the seconds field has no effect beyond the minute. |
| `pip-audit` for `croniter==7.0.0` and `jsonschema[format]==4.23.0` | docs | Closing task 4.2, with `arq` and `redis`. |
| PostgreSQL connection errors are not in the default retry set of `supervise`, `run_worker` and `run_consumer` | fix-here | Task 2.1 passes its driver's error classes through `retry_on` when the real `SourceStore` lands; the retry set is injectable and tested. |
| An abort (`Job.abort`) or an outer arq timeout cancels a job without requeueing it; the run lock is then held up to `max(lease_ttl, attempt_timeout)` | docs | Bounded, not a leak; aborts are not enabled (`allow_abort_jobs` is off). |
| `GET /health` binds `0.0.0.0`, has no connection cap and names the failing dependency unauthenticated | wont-fix | It runs inside the container network and the port is not published in compose; each connection is bounded to 5 s. Keep the port unpublished. |
| Waiting for cancelled jobs before `Worker.close()` cannot be pinned by a test | wont-fix | arq merges the job and main-task cancels of a graceful stop into one delivery; the wait stays as a guard against an interrupted requeue. |
| `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `COMPOSE_INTERNAL_HOSTS` in `.env.example` (listed in task 4.1) | new-item | Nothing in this change reads them; they belong to the fetch and proxy code in `scraper-v1`. Documenting them now would describe settings that do nothing. `CONTRACTS_DIR` is documented in `scraper/.env.example`. |
| Note to C for the `.docs/integration-plan.md` §7 variable list: the scraper reads `REDIS_URL`, `CONTRACTS_DIR`, `SCRAPER_CONSUMER` and `SCRAPER_<FIELD>` tuning variables (`scraper/.env.example`) | docs | For the human to pass on; §7 is C's section. |
| `pip-audit` (2026-11-21): `arq`, `redis`, `croniter`, `jsonschema`, `noble-tls` clean; `pytest 8.3.4` (dev only) had PYSEC-2026-1845, fixed by `pytest 9.0.3` with `pytest-asyncio 1.5.0` (all tests pass) | docs | Re-run before merge; the bump touches `scraper/requirements-dev.txt`, which `scraper-v1` also edits. |
| Consumer claim idle time, scheduler tick and sweep intervals and the health host and port are constructor arguments, not `SCRAPER_*` env settings | fix-here | Add them to `QueueSettings`/`RunnerSettings` and `.env.example` when the composition root is wired (2.1/3.3). |
| A flood of `iw:scan-requests` is unbounded | new-item | For C: the API side rate-limits requests and caps the stream with `MAXLEN`. |
| A malformed message that raises in the consumer could loop | fix-here | Task 2.1: isolate per-message errors once the store's error classes exist. |
| Uppercase UUIDs in a scan request are refused as `invalid_request` | wont-fix | Contract §7 uses lowercase UUID v4. |
| `SCRAPER_*` values are not range-validated (`DOMAIN_CONCURRENCY=0` requeues jobs forever) | wont-fix | Hackathon scope; the defaults are sane and config is set by the team. |
| Log redaction of `http://u:p@ss@host` and `scheme://token@host`, `redis://:pw@host`, `password=x` | docs | Fixed in this change with tests (`test_logs.py`). |
