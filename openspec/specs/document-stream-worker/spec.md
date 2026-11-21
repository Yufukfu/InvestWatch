# document-stream-worker Specification

## Purpose
Run the pure analytics pipeline as a service. Each document announced on Redis Stream `iw:documents` (`.docs/integration-plan.md` §2, point 3) is analyzed exactly once in effect. A message is acknowledged only when its findings are durable. Poison messages are acknowledged too, so they never block the stream.
## Requirements
### Requirement: Consumer group
The worker SHALL read `iw:documents` through the consumer group `analytics`, using XREADGROUP with a consumer name from `WORKER_CONSUMER` (default: the hostname). At startup it SHALL create the group from id `0` with MKSTREAM when the group does not exist, and SHALL treat an existing group as success.

#### Scenario: First start on an empty Redis
- **WHEN** the worker starts and neither the stream nor the group exists
- **THEN** both are created and the worker blocks waiting for messages

#### Scenario: Group already exists
- **WHEN** the worker starts and the group `analytics` already exists
- **THEN** startup continues without error and the group's last-delivered id is unchanged

#### Scenario: Backlog from before the first start
- **WHEN** documents were added to `iw:documents` before the group existed
- **THEN** the worker processes them as well

### Requirement: Acknowledge only after commit
For a valid message `{document_id, schema: "v1"}` the worker SHALL load the document, run `analyze`, and store all its findings in one committed transaction. It SHALL then publish the events and only then XACK the message. A failure before the commit SHALL leave the message pending and unacknowledged.

#### Scenario: Happy path
- **WHEN** a message for a committed `firm_own` document is read
- **THEN** one M2 finding row is committed, one `finding.created` event is published, and the message is acknowledged, in that order

#### Scenario: Document produces no finding
- **WHEN** the document is `third_party` and the pipeline returns no findings
- **THEN** nothing is stored or published, the message is acknowledged, and the log names the pipeline's reason

#### Scenario: Crash between commit and XACK
- **WHEN** the process dies after the commit and before XACK
- **THEN** the message stays pending and is redelivered later, and that redelivery is handled as a duplicate delivery

### Requirement: Duplicate delivery is idempotent
A redelivered message, or a second message for the same `document_id` (the scraper's republish sweep, a manual re-XADD), SHALL be analysed again and saved through the `(document_id, module)` upsert, so its findings are reported `updated` and publish no event. Two deliveries of the same message SHALL leave the same finding rows (same ids, `status`, `note`, `detected_at`) and the same events as one delivery; only the analysis fields and `updated_at` are refreshed. The outcome is logged as `stored` with `created: 0` and the number updated.

#### Scenario: Same message delivered twice
- **WHEN** the same `document_id` is delivered twice, sequentially or by two consumers
- **THEN** exactly one finding per module exists and exactly one `finding.created` event per finding was published

#### Scenario: Re-analysis after a pipeline fix
- **WHEN** a processed `document_id` is XADDed again after the rules changed
- **THEN** its finding keeps its `id` and `status`, carries the new score and rules, and no event is published

### Requirement: Poison messages
The worker SHALL acknowledge, without storing or publishing anything, a message that can never succeed. It SHALL log one JSON line at level `WARNING` with the stream message id, the `document_id` if known, and one of these reasons: `invalid_message` (missing or non-UUID `document_id`, `schema` other than `v1`, an undefined field, or bytes that are not UTF-8, which are decoded with replacement and then fail these checks), `document_not_found` (no row with that id), `invalid_document` (the row fails `ScrapedDocument` validation, or its `text` plus `payload` exceed `MAX_DOCUMENT_BYTES`, default 2 MB, measured before the row is loaded; the log names the field), or `max_deliveries_exceeded` (the delivery count reached `MAX_DELIVERIES`, default 5, after repeated unexpected errors).

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

#### Scenario: Oversized document
- **WHEN** a row's `text` plus `payload` exceed `MAX_DOCUMENT_BYTES`
- **THEN** it is acknowledged with reason `invalid_document` naming `text`, without the row being parsed

#### Scenario: Poison message does not stop the loop
- **WHEN** a poison message is followed by a valid one
- **THEN** the valid message is processed normally

### Requirement: Reclaim stale messages
The worker SHALL periodically run XAUTOCLAIM on the group for messages idle longer than `CLAIM_MIN_IDLE_MS` (default 60000), and process each claimed message like a new one. It SHALL count deliveries from the pending entry list.

#### Scenario: Consumer died mid-message
- **WHEN** consumer `a` read a message and stopped before XACK, and the idle time passes `CLAIM_MIN_IDLE_MS`
- **THEN** consumer `b` claims it, processes it and acknowledges it

#### Scenario: Message not yet stale
- **WHEN** a pending message has been idle for less than `CLAIM_MIN_IDLE_MS`
- **THEN** it is not claimed

### Requirement: Infrastructure outages
The worker SHALL survive an unreachable Redis or Postgres. It SHALL log the reason `redis_unavailable` or `db_unavailable`, retry with capped exponential backoff (1 s doubling up to 30 s, plus jitter, reset after a successful iteration), never acknowledge a message it could not commit, and resume without a restart once the dependency is back. Startup SHALL fail fast, with exit code 2 and an error naming the variable, when `DATABASE_URL` or `REDIS_URL` is missing, `DATABASE_URL` cannot be parsed (without quoting it), or the registry or catalogue fails to load.

#### Scenario: Postgres down while processing
- **WHEN** the store raises a connection error while loading the document or committing the findings
- **THEN** the message is not acknowledged, the worker backs off and retries, and after Postgres returns the message is processed once

#### Scenario: Redis down
- **WHEN** Redis is unreachable during XREADGROUP
- **THEN** the worker logs `redis_unavailable`, backs off without exiting, and resumes reading when Redis returns

#### Scenario: Missing configuration
- **WHEN** `DATABASE_URL` is unset at startup
- **THEN** the process exits non-zero with an error naming `DATABASE_URL`

### Requirement: Rules-only service run
The worker SHALL call `analyze` with the registry and catalogue loaded once at startup and `now` set to the current UTC time. Every finding it stores SHALL have `model.llm = null` while no LLM layer exists.

#### Scenario: No LLM configured
- **WHEN** the worker processes any document
- **THEN** the stored finding has `model.llm` null and `model.pipeline_version` set

### Requirement: Observability and graceful stop
The worker SHALL log JSON lines to stdout, never using `print`. One line per message SHALL carry the stream id, `document_id`, outcome (`stored`, `no_findings`, `retry_later` or a poison reason), the numbers of findings created and updated, and the duration in ms. It SHALL serve `GET /health` on `HEALTH_PORT` (default 8001), returning 200 with `{"status": "ok", "redis": true, "db": true}` when both dependencies answer and 503 with the failing one marked `false` otherwise. On SIGTERM or SIGINT it SHALL finish the current message and exit 0.

#### Scenario: Health with Postgres down
- **WHEN** `/health` is called while Postgres is unreachable
- **THEN** it answers 503 with `"db": false`

#### Scenario: Shutdown mid-message
- **WHEN** SIGTERM arrives while a message is being processed
- **THEN** that message is committed and acknowledged (or left pending if it failed), and the process exits 0 without reading another

### Requirement: Container
`analytics/Dockerfile` SHALL build from `python:3.13-slim` through the `public.ecr.aws/docker/library` mirror and run the worker as a non-root user. It SHALL take all configuration from env (`DATABASE_URL`, `REDIS_URL`, `REGISTRY_CSV`, `LOG_LEVEL`, `WORKER_CONSUMER`, `HEALTH_PORT`, `CLAIM_MIN_IDLE_MS`, `MAX_DELIVERIES`, `STREAM_BLOCK_MS`, `MAX_DOCUMENT_BYTES`) and declare a HEALTHCHECK on `/health`. The compose service SHALL join only infra's internal `data` network while the worker makes no outbound call, and SHALL NOT import test-only helpers (`InMemoryStore`, `NoopPublisher`).

#### Scenario: Image runs as non-root
- **WHEN** the image is built and `id -u` runs inside it
- **THEN** the uid is not 0

#### Scenario: Service in compose
- **WHEN** `docker compose up --build` runs with Redis and the migrated Postgres available
- **THEN** the `analytics` container becomes healthy, and a document XADDed to `iw:documents` yields a `findings` row

#### Scenario: No route out
- **WHEN** the compose configuration is rendered
- **THEN** the `analytics` service is attached to `data` only, not to `egress` or `edge`

#### Scenario: Test helpers are not loaded by the service
- **WHEN** `investwatch_analytics.worker` is imported
- **THEN** `investwatch_analytics.testing` is not among the loaded modules

### Requirement: Bundled registry is flagged
At startup the worker SHALL log one WARNING with reason `registry_seed` when the registry it loaded is the bundled fictional `registry/seed.csv`, saying that R1 results and high-risk alerts for real firms are not meaningful until a real KNF registry is set through `REGISTRY_CSV`. It SHALL NOT log it when `REGISTRY_CSV` names another file. R1 itself is unchanged.

#### Scenario: Default registry
- **WHEN** the worker starts without `REGISTRY_CSV`
- **THEN** one WARNING with reason `registry_seed` names `REGISTRY_CSV` and the seed path

#### Scenario: Real registry configured
- **WHEN** `REGISTRY_CSV` points to another valid registry file
- **THEN** no `registry_seed` warning is logged

