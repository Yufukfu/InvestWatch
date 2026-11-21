# Spec Delta

## MODIFIED Requirements

### Requirement: Duplicate delivery is idempotent
A redelivered message, or a second message for the same `document_id` (the scraper's republish sweep, a manual re-XADD), SHALL be analysed again and saved through the `(document_id, module)` upsert, so its findings are reported `updated` and publish no event. Two deliveries of the same message SHALL leave the same finding rows and the same events as one delivery.

#### Scenario: Same message delivered twice
- **WHEN** the same `document_id` is delivered twice, sequentially or by two consumers
- **THEN** exactly one finding per module exists and exactly one `finding.created` event per finding was published
- **AND** the rows keep the same ids, `status`, `note` and `detected_at`; only the analysis fields and `updated_at` are refreshed
- **AND** the second delivery is logged as `stored` with `created: 0` and the number updated

#### Scenario: Re-analysis after a pipeline fix
- **WHEN** a processed `document_id` is XADDed again after the rules changed
- **THEN** its finding keeps its `id` and `status`, carries the new score and rules, and no event is published

### Requirement: Poison messages
The worker SHALL acknowledge, without storing or publishing anything, a message that can never succeed. It SHALL log one JSON line at level `WARNING` with the stream message id, the `document_id` if known, and one of the reasons `invalid_message`, `document_not_found`, `invalid_document` or `max_deliveries_exceeded` (the delivery count reached `MAX_DELIVERIES`, default 5, after repeated unexpected errors).

#### Scenario: Malformed message
- **WHEN** a message has no `document_id`, a `document_id` that is not a lowercase UUID, a `schema` other than `v1`, or a field the contract does not define
- **THEN** it is acknowledged with reason `invalid_message`

#### Scenario: Missing document row
- **WHEN** `document_id` is a valid UUID that is not in `documents`
- **THEN** it is acknowledged with reason `document_not_found` and no finding exists

#### Scenario: Invalid document
- **WHEN** the row's `url` is not an absolute http(s) URL, or its `payload` holds a malformed block
- **THEN** it is acknowledged with reason `invalid_document`, and the log names the failing field

#### Scenario: Pipeline keeps crashing
- **WHEN** `analyze` raises an unexpected exception for a document on every attempt
- **THEN** the message is left pending (logged `retry_later` at `ERROR`) on each attempt below `MAX_DELIVERIES`, and acknowledged with reason `max_deliveries_exceeded` (at `ERROR`, with the traceback) on the attempt that reaches it

#### Scenario: Message with bytes that are not UTF-8
- **WHEN** a writer XADDs a `document_id` whose bytes are not valid UTF-8
- **THEN** it is acknowledged with reason `invalid_message`, the worker does not crash, and the next message is processed
- **AND** the bytes are decoded with replacement first, so they fail the message checks instead of raising

#### Scenario: Oversized document
- **WHEN** a row's `text` plus `payload` exceed `MAX_DOCUMENT_BYTES` (default 2 MB)
- **THEN** it is acknowledged with reason `invalid_document` naming `text`, without the row being parsed
- **AND** the size is measured in the database before the row is loaded

#### Scenario: Poison message does not stop the loop
- **WHEN** a poison message is followed by a valid one
- **THEN** the valid message is processed normally

### Requirement: Infrastructure outages
The worker SHALL survive an unreachable Redis or Postgres. It SHALL log the reason `redis_unavailable` or `db_unavailable`, retry with capped exponential backoff, never acknowledge a message it could not commit, and resume without a restart once the dependency is back. Startup SHALL fail fast, with exit code 2 and an error naming the variable, on a configuration it cannot use.

#### Scenario: Postgres down while processing
- **WHEN** the store raises a connection error while loading the document or committing the findings
- **THEN** the message is not acknowledged, the worker backs off and retries, and after Postgres returns the message is processed once
- **AND** the backoff doubles from 1 s up to 30 s, plus jitter, and resets after a successful iteration

#### Scenario: Redis down
- **WHEN** Redis is unreachable during XREADGROUP
- **THEN** the worker logs `redis_unavailable`, backs off without exiting, and resumes reading when Redis returns

#### Scenario: Missing configuration
- **WHEN** `DATABASE_URL` is unset at startup
- **THEN** the process exits non-zero with an error naming `DATABASE_URL`
- **AND** the same holds, with exit code 2, when `REDIS_URL` is missing, `DATABASE_URL` cannot be parsed (the error never quotes it), or the registry or catalogue fails to load

### Requirement: Observability and graceful stop
The worker SHALL log JSON lines to stdout, never using `print`, with one line per message. It SHALL serve `GET /health` on `HEALTH_PORT` (default 8001), returning 200 when both dependencies answer and 503 with the failing one marked `false` otherwise. On SIGTERM or SIGINT it SHALL finish the current message and exit 0.

#### Scenario: Health with Postgres down
- **WHEN** `/health` is called while Postgres is unreachable
- **THEN** it answers 503 with `"db": false`

#### Scenario: Health with both dependencies up
- **WHEN** `/health` is called while Redis and Postgres answer
- **THEN** it answers 200 with `{"status": "ok", "redis": true, "db": true}`

#### Scenario: Shutdown mid-message
- **WHEN** SIGTERM arrives while a message is being processed
- **THEN** that message is committed and acknowledged (or left pending if it failed), and the process exits 0 without reading another
- **AND** each handled message was logged with the stream id, `document_id`, outcome (`stored`, `no_findings`, `retry_later` or a poison reason), the numbers of findings created and updated, and the duration in ms

### Requirement: Container
`analytics/Dockerfile` SHALL build from `python:3.13-slim` through the `public.ecr.aws/docker/library` mirror, run the worker as a non-root user, take all configuration from env and declare a HEALTHCHECK on `/health`. The compose service SHALL join only infra's internal `data` network while the worker makes no outbound call, and SHALL NOT import test-only helpers (`InMemoryStore`, `NoopPublisher`).

#### Scenario: Image runs as non-root
- **WHEN** the image is built and `id -u` runs inside it
- **THEN** the uid is not 0

#### Scenario: Service in compose
- **WHEN** `docker compose up --build` runs with Redis and the migrated Postgres available
- **THEN** the `analytics` container becomes healthy, and a document XADDed to `iw:documents` yields a `findings` row
- **AND** its configuration came only from env: `DATABASE_URL`, `REDIS_URL`, `REGISTRY_CSV`, `LOG_LEVEL`, `WORKER_CONSUMER`, `HEALTH_PORT`, `CLAIM_MIN_IDLE_MS`, `MAX_DELIVERIES`, `STREAM_BLOCK_MS`, `MAX_DOCUMENT_BYTES`

#### Scenario: No route out
- **WHEN** the compose configuration is rendered
- **THEN** the `analytics` service is attached to `data` only, not to `egress` or `edge`

#### Scenario: Test helpers are not loaded by the service
- **WHEN** `investwatch_analytics.worker` is imported
- **THEN** `investwatch_analytics.testing` is not among the loaded modules
