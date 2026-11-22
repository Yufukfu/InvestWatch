# Spec Delta

## MODIFIED Requirements

### Requirement: Retry transient failures in the queue only
The queue SHALL retry transient failures (`timeout`, HTTP 5xx) up to a cap with exponential backoff and jitter. A `Retry-After` hint may raise a delay and never shorten it. A job that exceeds its job timeout counts as a `timeout` failure and is retried like any other. No other component retries; the confirmation request of a removed page (`web-collection`) is not a retry.

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
- **WHEN** a job fails with `blocked`, `blocked_target` or HTTP 404 (`http_error`; a confirmed removal of a source with a stored document is not a failure, see below)
- **THEN** it is not retried and one job error is recorded

#### Scenario: Retry-After defers the whole domain
- **WHEN** a job meets a `Retry-After` on any status (a 429 that ends it as `blocked`, or a 503 that it retries), capped at the configured maximum
- **THEN** no job of that domain starts its source until the wait has passed, whichever worker holds it

#### Scenario: A lost connection is not a failure
- **WHEN** the connection to PostgreSQL or Redis is lost while a job runs
- **THEN** the job is requeued after a short delay, no attempt is used up and no job error is recorded, up to a configured number of requeues; after that it fails like a crashed job (`scan.finished` failed, lock released)

#### Scenario: Events are not repeated after a requeue
- **WHEN** a connection is lost after `scan.finished` was published, or while `scan.started` was being announced
- **THEN** the requeued job publishes no second `scan.finished`, and `scan.started` is published exactly once, before the finish

### Requirement: Derive run status and record it on the source
`data.status` SHALL be `ok` with no job error (a removal is not one), `failed` with no document and at least one job error, otherwise `partial`. When a job starts running the scraper SHALL set `sources.last_run_status` to `running`; at its final outcome it SHALL write `last_run_at` (UTC) and `last_run_status`. The number of new documents of the job is the `documents` field of `scan.finished`; there is no `documents_count` column (the API counts `documents` rows on read).

#### Scenario: Run ends with job errors
- **WHEN** a job ends with one document and one job error
- **THEN** `scan.finished` has `status = partial` and `sources.last_run_status = partial`

#### Scenario: Run produces nothing
- **WHEN** the fetch of a job fails with a block
- **THEN** `scan.finished` has `status = failed`, `documents = 0`, and `last_run_at` is set

#### Scenario: Last run counts
- **WHEN** a second job for the same source finds only duplicates
- **THEN** `scan.finished` has `documents = 0` and `status = ok`

#### Scenario: Removed page ends ok and is not requeued
- **WHEN** a job ends with a confirmed removal (`http_error` `HTTP 404`/`HTTP 410` row with the source URL) and no document
- **THEN** `scan.finished` has `status = ok`, `documents = 0`, `sources.last_run_status = ok`, and the job is not requeued
