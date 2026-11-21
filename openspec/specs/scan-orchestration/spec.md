# scan-orchestration Specification

## Purpose

Run collection through a queue, on a schedule and on request, report progress to the API, and stay scalable and stable. Message shapes are in `contracts/schemas/events.schema.json` and `.docs/integration-plan.md` §5-§6 and are referenced, not restated.

## Requirements

### Requirement: Run collection through a job queue
Every collection SHALL run as a queued job. The queue SHALL cap the number of jobs running at once per domain across all workers (a counting semaphore in Redis with expiring leases) and SHALL resume jobs that were pending when a worker stopped.

#### Scenario: Per-domain concurrency is bounded
- **WHEN** more jobs for one domain are queued than the configured concurrency cap, spread over two workers
- **THEN** no more than the cap run at the same time, and a lease left by a crashed worker expires on its own

#### Scenario: Pending jobs survive a restart
- **WHEN** a worker stops while jobs are queued
- **THEN** those jobs run after it restarts, or on another worker, without being enqueued again

### Requirement: Retry transient failures in the queue only
The queue SHALL retry transient failures (`timeout`, HTTP 5xx) up to a cap with exponential backoff and jitter. A `Retry-After` hint may raise a delay and never shorten it. A job that exceeds its job timeout counts as a `timeout` failure and is retried like any other. No other component retries.

#### Scenario: Transient failure is retried
- **WHEN** a job fails with `timeout` or HTTP 503 and the retry cap is not reached
- **THEN** it is retried after a growing delay and no job error is recorded for that attempt

#### Scenario: Retry-After raises the delay
- **WHEN** the backoff is 2 seconds and the server asks for 20
- **THEN** the retry starts no earlier than 20 seconds later

#### Scenario: Retry cap reached
- **WHEN** a transient failure persists to the retry cap
- **THEN** one job error with the failing reason (`timeout` or `http_error`) is recorded

#### Scenario: Non-transient failure is not retried
- **WHEN** a job fails with `blocked`, `blocked_target` or HTTP 404
- **THEN** it is not retried and one job error is recorded

### Requirement: One run per source at a time
A job SHALL hold a per-source lock in Redis from its first attempt until its final outcome, renewed while the job is alive, so a retry backoff never lets another job in. A job for a source whose lock is held is dropped as coalesced. A lock left by a crashed worker expires on its own.

#### Scenario: Overlapping runs coalesce
- **WHEN** a scheduled job and a requested job for the same source start together
- **THEN** one runs and the other is dropped without a request to the site

#### Scenario: Lock held across retries
- **WHEN** a job is waiting out a retry backoff and a second job for the same source starts
- **THEN** the second job is dropped as coalesced and publishes nothing

#### Scenario: Stale lock after a crash
- **WHEN** a worker crashes mid-run and the lock time-to-live passes
- **THEN** the next job for that source runs

### Requirement: Run scans on request
The scraper SHALL read `scan_request` messages from Redis Stream `iw:scan-requests` through a consumer group with a stable consumer name per worker, enqueue a job for the named source, and acknowledge the message once the job is enqueued or refused; the job carries a `requested` flag. It SHALL claim messages that another consumer left pending longer than a configurable idle time.

#### Scenario: Request enqueues a job
- **WHEN** a valid scan request for an active `web` source arrives
- **THEN** one job for that source is enqueued and the message is acknowledged

#### Scenario: Invalid request with a source id
- **WHEN** a request names a source that does not exist, is inactive, or is not `web`
- **THEN** no request is made to any site, a job error with reason `invalid_request` is recorded, `scan.finished` with `status = failed` and `documents = 0` is published for that `source_id`, and the message is acknowledged

#### Scenario: Malformed request
- **WHEN** a message has no valid `source_id`
- **THEN** a job error with reason `invalid_request` is recorded with no source reference, nothing is published, and the message is acknowledged

#### Scenario: Crash before acknowledgement
- **WHEN** a worker reads a request and stops before acknowledging
- **THEN** another worker, or the same one after restart, claims the pending message and enqueues the job

### Requirement: Report scan progress
For every job that runs, scheduled or requested, the scraper SHALL publish `scan.started` once at the start and `scan.finished` once after its final outcome, as `event` envelopes on Redis Pub/Sub `iw:events`; retries inside a job do not publish again. `data.documents` is the count of newly inserted rows of that job (duplicates do not count).

#### Scenario: Requested job that cannot run
- **WHEN** a requested job starts and its source was deactivated after enqueue
- **THEN** no request is made and `scan.finished` with `status = failed` and `documents = 0` is published; a scheduled job in the same situation publishes nothing

#### Scenario: Deferred job waits silently
- **WHEN** a job meets a `Retry-After` deferral, a paused domain or an all-proxies-cooling state
- **THEN** it is requeued with a delay and publishes no event until it actually runs

#### Scenario: Events once per job
- **WHEN** a job fails twice with a timeout and succeeds on the third attempt
- **THEN** one `scan.started` and one `scan.finished` are published

#### Scenario: Scheduled run reports progress
- **WHEN** a scheduled job starts and ends
- **THEN** `scan.started` and `scan.finished` appear on `iw:events`, each in the `{type, emitted_at, data}` envelope with `data.source_id` and `data.documents`

#### Scenario: Coalesced job is silent
- **WHEN** a job is dropped because another run of the source holds the lock
- **THEN** it publishes nothing, and the running job's own events cover the source

### Requirement: Derive run status and record it on the source
`data.status` SHALL be `ok` with no job error, `failed` with no document and at least one job error, otherwise `partial`. When a job starts running the scraper SHALL set `sources.last_run_status` to `running`; at its final outcome it SHALL write `last_run_at` (UTC) and `last_run_status`. The number of new documents of the job is the `documents` field of `scan.finished`; there is no `documents_count` column (the API counts `documents` rows on read).

#### Scenario: Run ends with job errors
- **WHEN** a job ends with one document and one job error
- **THEN** `scan.finished` has `status = partial` and `sources.last_run_status = partial`

#### Scenario: Run produces nothing
- **WHEN** the fetch of a job fails with a block
- **THEN** `scan.finished` has `status = failed`, `documents = 0`, and `last_run_at` is set

#### Scenario: Last run counts
- **WHEN** a second job for the same source finds only duplicates
- **THEN** `scan.finished` has `documents = 0` and `status = ok`

### Requirement: Schedule collection and the republish sweep
Exactly one scheduler tick SHALL enqueue each due job, however many workers run, by using a unique job id per source and cron slot. The scheduler SHALL re-read `sources` every minute so changed or deactivated sources apply without a restart. The republish sweep SHALL run on a configurable interval.

#### Scenario: Cron fires once with two workers
- **WHEN** a source has `schedule_cron = "*/5 * * * *"`, two workers run, and a five-minute boundary passes
- **THEN** exactly one job for it is enqueued

#### Scenario: Changed cron applies
- **WHEN** a source's `schedule_cron` is edited
- **THEN** the next planning uses the new value within one minute

#### Scenario: Invalid cron expression
- **WHEN** a source has `schedule_cron = "not a cron"`
- **THEN** it is not scheduled and one job error with reason `invalid_request` is recorded until the value changes

#### Scenario: Sweep interval
- **WHEN** the configured sweep interval elapses
- **THEN** the sweep runs without a manual trigger

### Requirement: Scale out without coordination code
Workers SHALL be stateless: all shared state (queue, locks, rate limits, deferrals, cooldowns) lives in Redis or PostgreSQL, so adding workers needs only a replica count.

#### Scenario: Two workers, one source requested twice
- **WHEN** two workers run and two scan requests for the same source arrive together
- **THEN** exactly one document is inserted for an unchanged page, however the two jobs interleave

### Requirement: Stay stable under failure
A worker SHALL stop gracefully on SIGTERM by finishing or requeueing its running jobs within a configurable deadline, SHALL end any job that exceeds its job timeout with a `timeout` outcome, and SHALL reconnect to Redis and PostgreSQL with backoff instead of exiting.

#### Scenario: SIGTERM during a run
- **WHEN** a worker receives SIGTERM while a job runs
- **THEN** the job finishes or is requeued before the deadline and no job is lost

#### Scenario: Job exceeds its timeout
- **WHEN** an attempt runs longer than the job timeout
- **THEN** it is ended and the outcome is `timeout`, which the queue retries up to the cap; the lock is released after the final outcome

#### Scenario: Redis restarts
- **WHEN** Redis is unavailable for 10 seconds
- **THEN** the worker stays up, `/health` reports Redis as down meanwhile, and it resumes work when Redis returns

### Requirement: Be operable
The scraper SHALL expose `GET /health` and SHALL write every log line as single-line JSON to stdout.

#### Scenario: Healthy
- **WHEN** PostgreSQL, Redis and MinIO are reachable
- **THEN** `GET /health` returns 200

#### Scenario: Dependency down
- **WHEN** any of PostgreSQL, Redis or MinIO is unreachable
- **THEN** `GET /health` returns 503 and its body names the failing dependency

#### Scenario: Log format
- **WHEN** the scraper logs an event
- **THEN** the line parses as one JSON object
