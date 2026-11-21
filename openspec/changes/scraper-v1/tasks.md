# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 11 are docs, agreements and one spike: no test, no mutation check. Tests that need Redis, PostgreSQL or MinIO run against `docker compose` services (compose file: task 1.4).

## 1. ADRs and agreements

- [x] 1.1 Read the installed noble-tls, curl_cffi and httpx APIs and the in-house crawler repos; write ADR 0101 (`noble-tls`, `curl_cffi` fallback, Python 3.12); docs-check passes
- [x] 1.2 Write ADR 0102 (`arq`); ADR 0103 stays criteria-only and is decided in `scraper-v2`; docs-check passes
- [ ] 1.3 Agree with C on the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum `playwright|httpx|api|manual`; field not required; interim proposal `httpx` plus `scrape_meta.client`, or a v1 enum addition with `IW_CONTRACT_CHANGE=1` and a version bump); record in ADR 0101 and `contracts/`. Blocks nothing
- [ ] 1.4 Agree with C: who writes the Alembic migration (unique index `(source_id, content_hash)`, `job_errors` with nullable `source_id` and no foreign key, the published marker with its commit time, `sources.last_run_status` and `documents_count`), who provides `docker-compose.yml` (postgres, redis, minio), and that `.docs/integration-plan.md` §3 and §6 are stale against the schemas; also confirm that `documents.source_id` and `content_hash` are real columns and that the dashboard reads `sources.documents_count` as the last job's new documents; record in `.docs/STATUS.md`. Blocks groups 5-10; groups 4 and 8 may use a Redis started with `docker run` until the compose file lands
- [ ] 1.5 Spike (no production code): from the installed `noble-tls`, record in ADR 0101 Consequences whether it takes an explicit header order, manual redirects, resolved-IP pinning and body streaming; if a hard requirement of the specs fails, supersede ADR 0101 with `curl_cffi` before group 2

## 2. Skeleton, parser, site registry, error model

- [ ] 2.1 Failing test, then `scraper/` package with pinned deps on Python 3.12, a pytest setup and a Dockerfile whose context includes `contracts/` and that pre-warms the library of the client chosen in 1.5 at build; `pytest scraper` runs green in the image
- [ ] 2.2 Save the real KNF warnings page as a fixture (`scraper/tests/fixtures/`), plus article, no-title, windows-1250, empty and malformed fixtures; failing tests, then the parser (title with `<h1>` fallback, `canonical_url`, link filtering); the parse scenarios pass
- [ ] 2.3 Failing tests, then the host-keyed parser registry with the generic parser as default; the registry scenarios pass
- [ ] 2.4 Failing tests, then typed `JobError` with the closed reason set, an in-memory sink, the JSON logger and redaction of `user:pass@` URLs; the closed-set and string-level no-credentials tests pass
- [ ] 2.5 Mutation check; `mutations:`

## 3. Fetch layer (single attempt)

- [ ] 3.1 Failing tests, then `fetch(url, identity, proxy)` with timeout, manual redirect hops, streaming size cap, non-HTML rejection and charset decoding, against a local stub server; the timeout, http_error, no-retry, oversized, non-HTML and charset scenarios pass. Manual probe of the KNF page recorded in the AI log
- [ ] 3.2 Failing tests, then block detection (403, 429, captcha marker including a 200 block page, empty body); the blocked scenarios pass
- [ ] 3.3 Mutation check; `mutations:`

## 4. Identity, proxy, politeness (Redis)

- [ ] 4.1 Failing tests, then the identity table (lowercase header order per browser version, one version constant for user agent, `sec-ch-ua` and TLS profile) with a load-time pairing check, and a fresh session per attempt; the header-order test against a raw-socket stub, pairing, no-cookie-carry-over and identity-per-run scenarios pass
- [ ] 4.2 Failing tests, then the proxy rotator (`per_request` default, random start, never the same twice in a row, `PROXY_COOLDOWN_SECONDS` on 407, deferral when all cool, `per_session`, empty list); the proxy scenarios pass
- [ ] 4.3 Failing tests, then `robots.txt` handling (401/403/404/410 allow, 429/5xx/timeout disallow, never a block signal) and a Redis token-bucket per-domain rate limit with a local fallback; the robots and cross-worker rate-limit scenarios pass
- [ ] 4.4 Failing tests, then `Retry-After` (seconds and HTTP-date, cap, domain deferral in Redis) the per-domain failure cooldown by final job outcome, and requeue-with-delay for deferred jobs; the Retry-After, paused-domain and deferral scenarios pass with a fake clock
- [ ] 4.5 Mutation check; `mutations:`

## 5. Source selection and target guards (after 1.4)

- [ ] 5.1 Failing tests, then selection of active `web` sources with `source_kind` copied from the row, `schedule_cron = null` as manual only, and the active re-check at job start; the selection scenarios pass
- [ ] 5.2 Failing tests, then the URL guard (`http(s)` only, host allow-list with `www.` equivalence for redirects and scraped links); the allow-list, redirect, apex-to-www and non-http scenarios pass
- [ ] 5.3 Failing tests, then the address guard (own DNS resolution, refused ranges incl. IPv6 and mapped forms, compose names, connect to the checked address); the internal-address and DNS-change scenarios pass with a fake resolver
- [ ] 5.4 Mutation check; `mutations:`

## 6. Document build and insert (after 1.4)

- [ ] 6.1 Failing tests, then building the full document (`id` UUID v4, `fetched_at`, `scrape_meta` with `duration_ms` and proxy id, `source_id`) from a parsed page; contract-minimum fields present
- [ ] 6.2 Failing tests, then schema validation against `CONTRACTS_DIR`; the valid and `schema_invalid` scenarios pass (needs `contracts/requirements.txt`)
- [ ] 6.3 Failing tests, then `content_hash` over the normalised text, a dedup check, and insert with `ON CONFLICT DO NOTHING` returning an `IngestResult`; rerun, whitespace-only, case and changed-page scenarios pass against a real PostgreSQL
- [ ] 6.4 Mutation check; `mutations:`

## 7. Storage, publish, sweep, error sink

- [ ] 7.1 Failing tests, then bucket creation at startup, HTML upload to `iw-raw`, `html_object_key`, and object removal on a conflict or any later insert error; stored, `storage_error`, no-stray-object and insert-fails scenarios pass against a real MinIO
- [ ] 7.2 Failing tests, then `XADD iw:documents` after commit and `publish_failed` recording; the event-after-commit, insert-fails and Redis-down scenarios pass
- [ ] 7.3 Failing tests, then the republish sweep (unpublished and older than the grace period, `FOR UPDATE SKIP LOCKED`); the sweep, fresh-row, concurrent-sweeps and marker-failure scenarios pass
- [ ] 7.4 Failing test, then the database `job_errors` sink (nullable `source_id`); each reason is stored and no credential is recorded
- [ ] 7.5 Mutation check; `mutations:`

## 8. Queue, concurrency and run lock (ADR 0102)

- [ ] 8.1 Failing tests, then `arq` retries: backoff with jitter for `timeout` and 5xx only, `Retry-After` raising a delay, job timeout counted as `timeout`, one job error at the cap, deferral requeue without consuming a retry; the retry scenarios pass against a real Redis
- [ ] 8.2 Failing tests, then the per-domain concurrency cap (Redis counting semaphore with expiring leases) across two workers and resume of pending jobs after a worker stops; the concurrency, lease-expiry and restart scenarios pass. If resume fails, supersede ADR 0102
- [ ] 8.3 Failing tests, then the per-source Redis run lock held from first attempt to final outcome and renewed while alive; the overlap, lock-across-retries and stale-lock scenarios pass
- [ ] 8.4 Mutation check; `mutations:`

## 9. Runs, scan requests, schedule

- [ ] 9.1 Failing tests, then `run_source(source)` wiring guards, fetch, parse and ingest into a job outcome; the active re-check, deactivated-after-enqueue and manual-only scenarios pass over stubbed stages
- [ ] 9.2 Failing tests, then `scan.started`/`scan.finished` once per job on `iw:events` (silent for deferred and coalesced jobs, `failed` for a requested job that cannot run), status derivation, and `sources.last_run_status` (`running`), `last_run_at`, `documents_count`; the progress and status scenarios pass
- [ ] 9.3 Failing tests, then the `iw:scan-requests` consumer (stable consumer name, claim of stale pending messages, enqueue with the `requested` flag, `invalid_request` with `scan.finished` failed for a known uuid, silent malformed, ack); the scan-request scenarios pass against a real Redis
- [ ] 9.4 Failing tests, then the scheduler (cron to unique-id jobs, one enqueue with two workers, re-read each minute, `null` skipped, invalid cron recorded once) and the sweep on its interval; the schedule scenarios pass. First check that `arq` rejects a duplicate job id; if not, use a Redis `SET NX` slot key
- [ ] 9.5 Mutation check; `mutations:`

## 10. Stability, health and end to end

- [ ] 10.1 Failing tests, then graceful SIGTERM (finish or requeue before a deadline), the job timeout releasing the lock, and reconnect with backoff; the stability scenarios pass
- [ ] 10.2 Failing tests, then `GET /health` (200, or 503 naming the dependency) and single-line JSON logs on stdout; the operable scenarios pass
- [ ] 10.3 Failing end-to-end test on docker compose with the saved KNF page behind a local stub server and one worker: a seeded source yields a schema-valid `documents` row, a MinIO object, an `iw:documents` entry and `scan.finished`, and a rerun adds nothing. Fix only what this test shows, within this change's specs
- [ ] 10.4 Failing end-to-end test with two workers and two simultaneous scan requests for one source: exactly one `documents` row for an unchanged page, one `iw:documents` entry
- [ ] 10.5 Opt-in live smoke test (marker `scraper_live`, deselected by default and outside CI) fetching the real KNF page once through the full stack, plus a seed script that inserts the KNF `sources` row
- [ ] 10.6 Mutation check; `mutations:` (n/a for the end-to-end and smoke tests; list the guards 10.1-10.2 changed)

## 11. Closing

- [ ] 11.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md` stack lines, `iw-scraper-conventions` (session per attempt, proxy per request, a block ends the run and backoff is owned by the queue, not in-run identity rotation), the new env vars `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `COMPOSE_INTERNAL_HOSTS`, `CONTRACTS_DIR` in `.env.example` and a note to C for the §7 list, your row in `.docs/STATUS.md`, ADRs), run docs-check, and add the `iw-ai-log` row
- [ ] 11.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
