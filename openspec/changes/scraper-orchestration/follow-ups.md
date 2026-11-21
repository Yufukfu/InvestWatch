# Follow-ups

Findings of the `iw-reviewer` passes on group 1 (`bdeb218..77cb671`) and group 2 (`26a3cf1..bd6be4c`) and their declined-to-judge lists. Fixed findings are in the follow-up commit and not repeated here.

| Item | Disposition | Note |
|---|---|---|
| `run_source` raising leaves no job error and no domain outcome (the lock is released, arq logs the failure) | docs | Contract documented in `jobs.py`: collectors report failures as an `AttemptResult`. No `Reason` fits an internal error; revisit in task 2.1 when the real run is wired. |
| `CancelledError` releases the run lock, so a requeued job can lose its source to another job | fix-here | Decide in task 3.1 (SIGTERM): hand the lock over or leave it to its TTL. |
| A job that was mid-run when its worker was killed stays in progress until arq's in-progress key expires (about the job timeout plus 10 s) | fix-here | Task 3.1: shorter in-progress TTL or arq `health_check`; the spec scenario covers queued jobs only. |
| arq's own job timeout (`attempt_timeout` plus slack) is untested; only the inner `asyncio.timeout` is | fix-here | Task 3.1 ("job timeout releasing the lock"). |
| `iw:domain:*:failures` has no expiry, so "consecutive" has no time bound | wont-fix | The spec sets no time bound; a failure streak ends on the first success. |
| `iw:sem:*` keys are never deleted | wont-fix | One small key per domain, cosmetic. |
| Awaiting the cancelled lease keeper cannot be observed by a test | wont-fix | An in-flight renewal lands server-side either way; the await only guarantees the task has stopped. |
| `pip-audit` for `arq==0.28.0` and `redis` | docs | Run in closing task 4.2 before merge (hard rule). |
| Rate-limit token bucket and its Redis-down fallback, scheduler, scan requests, events, `/health` | docs | Later tasks (2.x, 3.x), out of scope for group 1. |
| `documents` of `scan.finished` and `sources.documents_count` count the final attempt only; rows inserted by an attempt that then failed transiently are not added | docs | Decision: a collector inserts rows when it succeeds, so a retried attempt has none to lose; revisit with the real ingest (2.1) if a partial attempt can insert. |
| A `CancelledError` reaching `execute_job` (shutdown, arq's outer timeout) leaves the started marker without a `scan.finished` | fix-here | Task 3.1 with the SIGTERM work, next to the lock hand-over. |
| A scan request redelivered after its job's arq result key expired (about 1 h) runs again | wont-fix | Needs a pending message older than the result retention; the claim idle time is far shorter. |
| `iw:cron-invalid:*` and `iw:started:*` keys: the first has no expiry | wont-fix | One small key per bad source, removed when the cron is fixed. |
| Who calls `ScanRequestConsumer.poll` and `Scheduler.run`, and whether they survive Redis or PostgreSQL errors | fix-here | Task 3.1/3.2 process wiring; `Scheduler.run` already logs and continues, `poll` does not catch yet. |
| `mark_running` / `mark_finished` idempotency in the PostgreSQL `SourceStore` | docs | Task 2.1 implements the store; `execute_job` calls each once per job. |
| `requested_at` is not validated and stale requests are not dropped | wont-fix | The spec asks only for a valid `source_id`. |
| `croniter` accepts a 6-field (seconds) expression; `schedule_cron` is a 5-field cron per the contract | wont-fix | Evaluated per minute, so the seconds field has no effect beyond the minute. |
| `pip-audit` for `croniter==7.0.0` and `jsonschema[format]==4.23.0` | docs | Closing task 4.2, with `arq` and `redis`. |
