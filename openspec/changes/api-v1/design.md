# Design

## Context

`api-db-schema` creates the `api/` package, the tables and the `api-migrate` step. The Caddy gateway already routes `/api`, `/api/*`, `/socket.io` and `/socket.io/*` to `api:8000` without stripping the prefix (`infra/gateway/Caddyfile`), with a 1 MB request body limit. The dashboard uses an RTK Query client generated from `contracts/openapi.yaml` ([ADR 0201](../../../.docs/decisions/0201-web-stack-and-generated-client.md)) and was built against the archived mock server (branch `contracts/mock-server`, `contracts/mock-server/src/iw_mock_server/`), which already implements every route on in-memory data with FastAPI + python-socketio, plus an OpenAPI response checker (`tests/openapi_check.py`). Redis and MinIO come from the parallel `infra-compose` change. See `proposal.md` for scope.

## Goals / Non-Goals

**Goals:**
- The dashboard switches from mocks to the API with no client change.
- Integration #1 path first: `GET /findings`, `GET /findings/{id}`, `PATCH`, thresholds, health and the relay (task groups 2-4); the rest follows for Integration #2.
- Each route testable against real Postgres and Redis, without the dashboard.

**Non-Goals:**
- Authentication, roles, rate limiting (open question 5).
- Writing findings or documents; computing calibration; consuming `iw:scan-requests`.

## Decisions

1. **One ASGI app: `socketio.ASGIApp(sio, other_asgi_app=fastapi_app)`, served by uvicorn on port 8000.** Same pattern as the mock server (`events.py`), so the dashboard's Socket.IO client settings carry over. All routes `async def` (mock-server follow-up 22: mixing thread-pool routes with loop-owned state caused races). Alternative: a separate relay process; rejected, it would need its own Socket.IO server and a Redis adapter for the PATCH events.
2. **Copy, not import, from the mock server.** Request models (`FindingPatch`, `Thresholds`, `SourceCreate`, `SourcePatch`, `ScanRequest`), the two exception handlers that produce `{error, details}`, the `_matches_text` field list and `openapi_check.py` move into `api/` and are adapted to SQL. The mock server stays a standalone dev tool; sharing code would couple two deployables (ADR 0202: modules meet only through network contracts).
3. **Async SQLAlchemy Core over psycopg 3** (ADR 0307), queries in `investwatch_api/queries/`, one module per resource. `risk_level` is a SQL `CASE` over `score` and the module's threshold passed as bound parameters, so filtering, counting (`by_risk_level`, trend) and pagination stay in one query and `total` is exact.
4. **Thresholds key format: a JSON string** `{"M1":0.6,"M2":0.5,"M3":0.7}`, the same shape as the OpenAPI `Thresholds` schema, read with `GET` and written with `SET`. Alternative: a Redis hash with fields `M1..M3` (`HGETALL`), which returns strings and allows a partial write. The format is not in `contracts/`, and analytics reads the same key, so it needs Damian's approval (open question 3). The API keeps the last value it read in memory only as a fallback for Redis outages (spec "Redis unavailable"); it never serves it while Redis answers, so a slider move is visible on the next request.
5. **`finding.updated` goes through `iw:events`, not straight to Socket.IO.** One delivery path for all events; several API replicas would all deliver it. Published after the DB commit; a publish failure is logged, not returned to the client (the status change is the user's intent and is already saved).
6. **Relay validation with `jsonschema` against `contracts/schemas/events.schema.json`,** loaded from `CONTRACTS_DIR` at start-up (fails fast if missing). Invalid messages are dropped with a warning. The relay never adds `risk_level` to the brief (ADR 0305: pass-through).
7. **Redis client `redis.asyncio`** (one client for thresholds, the scan stream, PATCH events and the Pub/Sub subscription). Reconnect loop with capped exponential backoff around the subscription; a module-level health flag feeds `/health`.
8. **MinIO through the `minio` SDK**, calls wrapped in `asyncio.to_thread` because the SDK is synchronous. The object key always comes from `documents.payload.screenshots[viewport]`, never from the URL, so a client cannot read arbitrary objects. Same SDK as the scraper.
9. **Defaults and edge rules the contract leaves open** (assumptions, record in `api/README.md`): `/stats/trend` without dates covers the last 24 hours for `hour` and the last 14 days for `day`; buckets are UTC; `date_to` is inclusive; `q` escapes `%`, `_` and `\` before `ILIKE`; `sort=score` ties break by `detected_at` descending then `id`; `documents_count` is a `COUNT` per source; `last_scan_at` is `max(sources.last_run_at)`; `/health` always returns 200 (the contract lists only 200) and shows the result in `status`; 503 with the error body is used when Redis or MinIO is needed and down, a status the contract does not list.
10. **Config from env only:** `DATABASE_URL` (as `iw_app`), `REDIS_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` (default `iw-raw`), `MINIO_SECURE` (default false), `CONTRACTS_DIR`, `CORS_ORIGINS` (empty: same origin only, which is the gateway case), `LOG_LEVEL`. MinIO variable names are aligned with `infra-compose` before group 6.
11. **Tests:** pytest with FastAPI's test client for REST, a real Postgres (fixture from `api-db-schema`) seeded from `contracts/mocks/`, and a real Redis when `TEST_REDIS_URL` is set; `fakeredis` only if its pub/sub works with `redis.asyncio` in the pinned versions (checked in task 1.2, otherwise tests skip without Redis). Socket.IO is tested with `socketio.AsyncClient` against uvicorn on a free port, as in the mock server's `test_events.py`. MinIO is faked behind a small `ObjectStore` interface; one manual check against the real MinIO in group 6.

## Risks / Trade-offs

- [Contract detail schema unsatisfiable (`allOf` with `additionalProperties: false` plus `document`)] → tests validate the finding and document parts separately, as the mock server did; listed as open question 1, no contract edit.
- [Redis down hides alerts] → health shows it, REST keeps answering, the dashboard refetches on reconnect.
- [Pub/Sub loses events while the API restarts] → acceptable for alerts; the table is the source of truth and the dashboard polls on reconnect. A Redis Stream for events would be a contract change.
- [Threshold key format mismatch with analytics] → one format in design decision 4, shared with the analytics-worker change before either is applied.
- [`ILIKE` on five fields gets slow] → fine at hackathon volume; a `pg_trgm` index is a later revision if needed.
- [No authentication on an API that changes statuses and sources] → only the gateway is exposed and only on `127.0.0.1` (ADR 0202); open question 5.

## Migration Plan

Needs `api-db-schema` applied and Redis/MinIO from `infra-compose`. `api` in `api/compose.yaml` depends on `api-migrate` (completed) and on Postgres and Redis being healthy. Rollback: point `web/` back to mock mode (its own env switch).

## Open Questions

1. `GET /findings/{id}` response schema in `contracts/openapi.yaml` combines `allOf: [finding.schema.json]` (which has `additionalProperties: false`) with extra `document` and `screenshot_urls`, so no real response can validate (mock-server follow-up 8). Fix in a contract v1.1, or accept split validation?
2. `SourceInput` has no `required` list, but `POST /sources` must return a full `Source` (mock-server follow-up 31). This change requires `name, platform, url, source_kind, target_modules` on POST, as the mock does. OK?
3. Value format of `iw:settings:thresholds`: JSON string (decision 4) or a hash? Should it be written into `contracts/` (analytics-plan §12.4 says "to be added to the contract")?
4. `GET /calibration`: only the latest gold-set run from `calibration_points`, or also live counts from analyst labels (`confirmed` / `false_positive`), as integration-plan §5 suggests? This design returns the stored run only.
5. Authentication for the demo: none behind the localhost gateway (this design), or a shared token?
6. Status transitions: any status to any status (this design), or a fixed workflow (for example no way back from `closed`)?
7. `/health`: should it also report `analytics`, `scraper` and `llm` like `contracts/mocks/health.json`? That needs a heartbeat convention (for example Redis keys with a TTL) that no service has yet; this design reports only `api`, `postgres`, `redis`, `minio`.
