# api (Damian's module)

REST API and Socket.IO gateway for the dashboard, and the owner of the shared Postgres schema (Alembic). Stack and placement: [ADR 0302](../.docs/decisions/0302-api-service.md); schema ownership: [ADR 0303](../.docs/decisions/0303-database-schema-ownership.md); driver and table layout: [ADR 0307](../.docs/decisions/0307-database-driver-and-table-layout.md); thresholds: [ADR 0305](../.docs/decisions/0305-threshold-storage.md). The logic lives in the docs, not here:

- Routes and shapes: [`contracts/openapi.yaml`](../contracts/openapi.yaml) and [`.docs/integration-plan.md`](../.docs/integration-plan.md) §5. Events: §6 and `contracts/schemas/events.schema.json`. `Finding` and `risk_level`: §4.
- What the schema guarantees: `openspec/specs/database-schema/spec.md`; tables and the SQL writers use: [`README.md`](README.md). REST and Socket.IO behaviour: `openspec/specs/rest-api/spec.md` and `openspec/specs/event-relay/spec.md`; run steps and edge rules: [`README.md`](README.md).

## Rules that are easy to get wrong

- The contract is frozen: serve `contracts/openapi.yaml` exactly. A gap in it is a question for the team, not a quiet extra field.
- Every table change is a new Alembic revision in `api/migrations/versions/`, run as `iw_admin`. Never edit an applied revision; never create tables from service code or init scripts.
- The service connects as `iw_app` (`DATABASE_URL`); only `alembic` uses `DATABASE_ADMIN_URL`.
- `risk_level` is derived on read from `score` and Redis `iw:settings:thresholds` (`high >= t`, `medium >= t - 0.2`, else `low`); it is never stored. The API writes that key; analytics only reads it.
- The relay forwards `iw:events` to Socket.IO `/events` unchanged; it applies no threshold logic. Drop messages that fail the events schema.
- Screenshot object keys come from the `documents` row, never from the request.
- Keep the mocks: the mock server (`contracts/mock-server/`) and the mocks (`contracts/mocks/`) stay as a test double for `web/` now that the real `api/` exists; removing or replacing them needs Damian's OK. Where the real API diverges (for example `/calibration`), record a follow-up instead of changing the mock.
- All routes `async def`; config from env only; JSON logs to stdout through the logger, no `print`; never log connection strings or keys.

## Stack and done

Python 3.13, FastAPI, python-socketio, SQLAlchemy 2 Core + psycopg 3, Alembic, `redis.asyncio`, `minio`; pytest against a real Postgres (and Redis when `TEST_REDIS_URL` is set). Done means `alembic upgrade head` works on an empty database, every route's response validates against `contracts/openapi.yaml`, and an `iw:events` message reaches a Socket.IO client through the gateway.
