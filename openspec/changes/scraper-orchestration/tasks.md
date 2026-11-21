# Tasks

Each group from 1 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Group 4 is docs only. Starts after `scraper-v1` and `scraper-ingest` are merged and C's migration and compose file exist; tests run against `docker compose` services.

## 1. Queue, concurrency and run lock (ADR 0102)

- [x] 1.1 Failing tests, then `arq` retries: backoff with jitter for `timeout` and 5xx only, `Retry-After` raising a delay, job timeout counted as `timeout`, one job error at the cap, deferral requeue without consuming a retry, and one domain outcome recorded per final job outcome (failure cooldown); the retry scenarios pass against a real Redis
- [x] 1.2 Failing tests, then the per-domain concurrency cap (Redis counting semaphore with expiring leases) across two workers and resume of pending jobs after a worker stops; the concurrency, lease-expiry and restart scenarios pass. If resume fails, supersede ADR 0102
- [x] 1.3 Failing tests, then the per-source Redis run lock held from first attempt to final outcome and renewed while alive; the overlap, lock-across-retries and stale-lock scenarios pass
- [x] 1.4 Mutation check; `mutations: 35 tried, 34 caught` (survivor: awaiting the cancelled lease keeper before the release, equivalent because an in-flight renewal lands server-side either way)

## 2. Runs, scan requests, schedule

- [x] 2.1 Failing tests, then `run_source(source_id)` loading the source row from PostgreSQL and wiring guards, fetch, parse and ingest into a job outcome; the active re-check at job start, deactivated-after-enqueue and manual-only scenarios pass over stubbed stages (`collect.py`, `pgstore.py`; the active re-check lives in `execute_job`); `mutations: 20 tried, 20 caught` (two survivors on the `Retry-After` digit guards got test cases)
- [x] 2.2 Failing tests, then `scan.started`/`scan.finished` once per job on `iw:events` (silent for deferred and coalesced jobs, `failed` for a requested job that cannot run), status derivation, and `sources.last_run_status` (`running`), `last_run_at` (no `documents_count`: the API counts rows); the progress and status scenarios pass
- [x] 2.3 Failing tests, then the `iw:scan-requests` consumer (stable consumer name, claim of stale pending messages, enqueue with the `requested` flag, `invalid_request` with `scan.finished` failed for a known uuid, silent malformed, ack); the scan-request scenarios pass against a real Redis
- [x] 2.4 Failing tests, then the scheduler (cron to unique-id jobs, one enqueue with two workers, re-read each minute, `null` skipped, invalid cron recorded once) and the sweep on its interval; the schedule scenarios pass. First check that `arq` rejects a duplicate job id; if not, use a Redis `SET NX` slot key
- [x] 2.5 Mutation check; `mutations: 43 tried, 43 caught`

## 3. Stability, health and end to end

- [x] 3.1 Failing tests, then graceful SIGTERM (finish or requeue before a deadline), the job timeout releasing the lock, and reconnect with backoff; the stability scenarios pass
- [x] 3.2 Failing tests, then `GET /health` (200, or 503 naming the dependency) and single-line JSON logs on stdout; the operable scenarios pass
- [x] 3.3 Failing end-to-end test on docker compose with the saved KNF page behind a local stub server and one worker: a seeded source yields a schema-valid `documents` row, a MinIO object, an `iw:documents` entry and `scan.finished`, and a rerun adds nothing. Fix only what this test shows, within this change's specs (`app.py`, `tests/test_e2e.py`; the `worker` and `scheduler` commands are `python -m iw_scraper worker|scheduler`); `mutations: 8 tried, 8 caught`
- [x] 3.4 Failing end-to-end test with two workers and two simultaneous scan requests for one source: exactly one `documents` row for an unchanged page, one `iw:documents` entry (`tests/test_e2e.py`, two workers and consumers)
- [ ] 3.5 Opt-in live smoke test (marker `scraper_live`, deselected by default and outside CI) fetching the real KNF page once through the full stack, plus a seed script that inserts the KNF `sources` row (`seed.py` with `mutations: 3 tried, 3 caught` and `tests/test_live.py` are written; the live run waits for a human go-ahead, as it makes a real request to knf.gov.pl)
- [x] 3.6 Mutation check; `mutations: 31 tried, 30 caught` (n/a for the end-to-end and smoke tests 3.3-3.5; guards of 3.1-3.2: supervisor, worker runner, cancel lock, health, log format and redaction. Survivor: waiting for cancelled jobs before `close()`, which only matters when a second cancel arrives after the first was delivered; arq merges the two in the same tick, so no test can force it. One mutant, the supervisor returning when its work returns, was confirmed by running its test by hand because the batch run mis-parsed the output)

## 4. Closing

- [ ] 4.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, `iw-scraper-conventions` (session per attempt, proxy per request, a block ends the run and backoff is owned by the queue, not in-run identity rotation), `CONTRACTS_DIR` and the `SCRAPER_*` settings in `.env.example` (done; `PROXY_*` and `COMPOSE_INTERNAL_HOSTS` belong to `scraper-v1`, see `follow-ups.md`) and a note to C for the §7 list, your row in `.docs/STATUS.md`), run docs-check, and add the `iw-ai-log` row
- [ ] 4.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
