# Follow-ups

Findings of the `iw-reviewer` pass on group 1 (`bdeb218..77cb671`) and its declined-to-judge list. Fixed findings are in the follow-up commit and not repeated here.

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
