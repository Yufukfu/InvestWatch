# Proposal

## Why

The change `analytics-skeleton` gives analytics a pure `analyze(doc, *, registry, catalogue, now) -> list[Finding]` with no I/O. Integration #1 (Sat 17:00) needs more: a document announced on `iw:documents` has to end up as a `findings` row and an `iw:events` message. This change adds that I/O layer (`.docs/analytics-plan.md` §12.3 steps 7-9), so analytics runs as a service under `docker compose`.

## What Changes

- Add `storage.py`. It defines a store interface with two implementations: Postgres and in-memory (for tests). The store loads a `ScrapedDocument` from `documents` (simple columns plus `payload JSONB`) and inserts or updates a document's findings in one transaction. A re-scan of the same URL updates the existing finding for that module, keeping its `id`, `detected_at` and analyst `status`. It does not insert a duplicate.
- Add `events.py`. It defines a publisher interface with a Redis Pub/Sub implementation on `iw:events` and a no-op publisher. A new finding publishes `finding.created`. It also publishes `finding.high_risk` when `score` is at or above the module threshold, read from Redis key `iw:settings:thresholds` on every finding with no cache. If the key or a module value is missing, the defaults M1 0.6 / M2 0.5 / M3 0.7 apply (ADR 0305). Payloads follow `contracts/schemas/events.schema.json` (`event` envelope, `finding_brief` data, no `risk_level`) and `.docs/integration-plan.md` §6.
- Add `worker.py`. It consumes Redis Stream `iw:documents` with consumer group `analytics` (created if missing). The loop is XREADGROUP, then load, analyze, store and commit, then publish, then XACK. XACK happens only after the commit. XAUTOCLAIM picks up messages left idle by a dead consumer. Poison messages are logged and acked with a reason: a malformed message, a missing document row, an invalid document, or one that keeps failing past a delivery limit. A duplicate delivery goes through the upsert, so the finding rows stay the same and no event is published again. If Redis or Postgres is down, the worker retries with backoff and never acks. Logs are JSON to stdout. The service runs rules-only, so `model.llm = null`.
- Add a minimal `/health` endpoint (stdlib HTTP) reporting Redis and Postgres reachability, as `.docs/integration-plan.md` §7 asks of every service.
- Add `analytics/Dockerfile` (`python:3.13-slim` from the `public.ecr.aws` mirror, uid 10001, HEALTHCHECK) and `analytics/compose.yaml`, which declares no network or database of its own: it references infra's `data` and `egress` networks, builds `DATABASE_URL` (app role) and `REDIS_URL` from the root `.env`, and waits on `api-migrate`, `postgres` and `redis`. One root `include:` line. The worker's env vars go into `analytics/.env.example`.
- Out of scope: the pipeline itself (rules, registry, M2 assembly; `analytics-skeleton`), the LLM layer and its Redis cache, modules M1/M3, the real KNF loader, the gold set, and calibration. Also out of scope: creating any table. Migrations belong to `api/` per ADR 0303. Redis, MinIO and the Postgres roles belong to `infra-compose` and `infra/`. Also out of scope: a dead-letter stream and an event outbox (design, resolved questions).
- Owner: Damian (`analytics/`).
- Contracts: reads the `documents` table (`ScrapedDocument` v1, integration point 1) and consumes the `document_message` stream envelope (point 3). Writes the `findings` table (`Finding` v1, point 4) and publishes the `event` envelope with types `finding.created` and `finding.high_risk` (point 5). Reads the Redis key `iw:settings:thresholds` written by the API (ADR 0305). It changes none of these shapes and no REST route.

## Dependencies and assumptions to reconcile

- **`analytics-skeleton` (parent change, not merged):** this change calls `analyze()` and the `ScrapedDocument` and `Finding` models, and loads the registry and catalogue the way that change does. It is applied only after `analytics-skeleton` is merged, and the branch is rebased on it.
- **`api-v1` / `api-db-schema` (sibling, Alembic, ADR 0303):** provides `documents` and `findings`. Reconciled in task 2.1 against `origin/api/api-db-schema` at `7af51ab` (design §"Table shape"): the upsert key `uq_findings_document_module (document_id, module)`, the replaced-field list, and the `iw_app` grants. The threshold key format (a JSON string written by the API) is agreed by the coordinator. `analytics/tests/sql/schema.sql` mirrors the migration for tests only.
- **`infra-compose` (PR #18, `chore/infra-compose-v2`):** provides Redis 8 with AOF (ADR 0305) and `REDIS_PASSWORD`, and the `data` (internal) and `egress` networks the worker joins. **Merge order:** this change merges after PR #18 (`redis`) and PR #15 (`api-migrate`, root `include` of `api/compose.yaml`); its root `include` line references both.
- **`scraper-v1` (Adam):** publishes to `iw:documents` only after the row is committed. Delivery is at least once, so analytics deduplicates by `document_id`.

## Capabilities

### New Capabilities
- `document-stream-worker`: consume `iw:documents` with consumer group `analytics` and acknowledge each message only once its findings are committed. Covers reclaiming idle messages, poison messages, duplicate deliveries, outages of Redis and Postgres, health, and the container.
- `finding-storage`: load a document by id and store a document's findings atomically. Re-analysing a document updates its finding per module instead of duplicating it.
- `finding-events`: publish contract-valid `finding.created` and `finding.high_risk` events, with thresholds read live from Redis.

### Modified Capabilities

## Impact

- New code under `analytics/` only: `src/investwatch_analytics/{storage,events,worker,health}.py`, `Dockerfile`, `compose.yaml`, `.dockerignore`, additions to `config.py` and `.env.example`, `tests/`.
- Dependencies: `psycopg[binary]` 3 and `redis` (redis-py). Dev: `fakeredis` for the unit tests. `analytics/tests/sql/schema.sql` (a test-only mirror of the API migration). Integration tests run against real Postgres and Redis when `TEST_DATABASE_URL` / `TEST_REDIS_URL` are set and are skipped otherwise. All pinned and checked with `pip-audit`.
- Root `compose.yaml`: one `include:` line for `analytics/compose.yaml`. The root file is Kacper's, so the line is announced in the team chat (infra rule: one line per module).
- Docs: `analytics/README.md` (run and env), `analytics/CLAUDE.md` if a rule turns out to be easy to get wrong, the analytics row of `.docs/STATUS.md`, an AI log row.
