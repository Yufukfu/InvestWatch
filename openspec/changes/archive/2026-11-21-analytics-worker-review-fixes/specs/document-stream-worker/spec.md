# Spec Delta

## ADDED Requirements

### Requirement: Bundled registry is flagged
At startup the worker SHALL log one WARNING with reason `registry_seed` when the registry it loaded is the bundled fictional `registry/seed.csv`, saying that R1 results and high-risk alerts for real firms are not meaningful until a real KNF registry is set through `REGISTRY_CSV`. It SHALL NOT log it when `REGISTRY_CSV` names another file. R1 itself is unchanged.

#### Scenario: Default registry
- **WHEN** the worker starts without `REGISTRY_CSV`
- **THEN** one WARNING with reason `registry_seed` names `REGISTRY_CSV` and the seed path

#### Scenario: Real registry configured
- **WHEN** `REGISTRY_CSV` points to another valid registry file
- **THEN** no `registry_seed` warning is logged

## MODIFIED Requirements

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
