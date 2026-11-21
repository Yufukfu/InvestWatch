# Proposal

## Why

The dashboard (`web/`, Kacper) is built against `contracts/openapi.yaml` and runs on mocks. Integration #1 (Sat 17:00) needs it to show a real finding and get a real-time alert, and Integration #2 needs filters, trend and status change on real data ([integration-plan.md](../../../.docs/integration-plan.md) §8). [ADR 0302](../../../.docs/decisions/0302-api-service.md) chose a separate FastAPI + python-socketio service in `api/`. This change builds it on the tables from change `api-db-schema`.

## What Changes

- Serve the 11 paths of `contracts/openapi.yaml` under `/api` exactly as specified (methods, query parameters, bodies, status codes, the `{error, details}` error shape), reading and writing the tables from `api-db-schema`.
- Derive `risk_level` on every finding response and in the `risk_level` filters from `score` and the current module threshold: `high` when `score >= t`, `medium` when `score >= t - 0.2`, otherwise `low` (integration-plan §4). It is never stored.
- Own the Redis key `iw:settings:thresholds` ([ADR 0305](../../../.docs/decisions/0305-threshold-storage.md)): `GET`/`PUT /settings/thresholds` read and write it, and the API writes the defaults when it is missing.
- `PATCH /findings/{id}` changes `status` and/or `note`, bumps `updated_at`, and publishes `finding.updated` on `iw:events`.
- `POST /scans` adds `{source_id, requested_at}` to Redis Stream `iw:scan-requests`.
- `GET /documents/{id}/screenshot/{viewport}` streams the PNG from MinIO bucket `iw-raw`.
- Relay every message on Redis Pub/Sub `iw:events` to Socket.IO namespace `/events`, with `type` as the event name and `data` as the payload (integration-plan §6), dropping messages that fail `contracts/schemas/events.schema.json`.
- `GET /health` reports the API and its dependencies (Postgres, Redis, MinIO).
- Add the `api` service to `api/compose.yaml` on `iw-edge` and `iw-data`, behind the Caddy gateway that already routes `/api` and `/socket.io` to `api:8000`.
- Reuse, by copying and adapting, the request models, error handlers, filter semantics and OpenAPI response checker of the archived mock server (`contracts/mock-server` branch), so the real API behaves like the mock the dashboard was built against.
- Owner: Damian (`api/`).
- Out of scope: authentication and roles (open question), the tables themselves (`api-db-schema`), writing findings or documents (analytics, scraper), the scheduler and the consumer of `iw:scan-requests` (scraper), computing calibration curves (analytics eval writes `calibration_points`), and the Redis/MinIO containers (`infra-compose`).

## Contracts

- Implements, without changing: all 11 REST paths of `contracts/openapi.yaml` v1.0.0, the Socket.IO events of `contracts/schemas/events.schema.json` (`finding.created`, `finding.high_risk`, `finding.updated`, `scan.started`, `scan.finished`), the `iw:scan-requests` stream message, and the `Finding`, `ScrapedDocument` and `Source` schemas.
- Publishes `finding.updated` on `iw:events` (integration-plan §6 lists it; the producer was not named).
- Two known contract gaps stay as they are (contracts are frozen) and are listed as open questions in `design.md`: the `GET /findings/{id}` response schema cannot be satisfied as written, and `SourceInput` has no required list for `POST /sources`.
- The value format of `iw:settings:thresholds` is not in `contracts/`; this change proposes one (design decision 4) for Damian to approve, because analytics reads the same key.

## Capabilities

### New Capabilities
- `rest-api`: the REST endpoints of `contracts/openapi.yaml`, including `risk_level` derivation, filtering, pagination, status changes, thresholds, sources, scans, screenshots and health.
- `event-relay`: forwarding `iw:events` to Socket.IO `/events`, and the events the API itself publishes.

### Modified Capabilities

## Impact

- Code in `api/src/investwatch_api/` (routes, queries, Redis and MinIO clients, Socket.IO) and `api/tests/`.
- Dependencies (pinned, `pip-audit` before merge): `fastapi`, `uvicorn[standard]`, `python-socketio`, `redis` (asyncio client), `minio`, `jsonschema[format]`; dev: `pytest`, `httpx`, `pyyaml`, `fakeredis` if its pub/sub support is enough, else a real Redis.
- `web/`: switches from mock mode to the real API through the gateway; no client regeneration, since the contract is unchanged.
- Analytics: must publish `finding.created` / `finding.high_risk` on `iw:events` in the event shape and read `iw:settings:thresholds` in the format of decision 4.
- Docs: `api/CLAUDE.md`, `api/README.md`, `.docs/integration-plan.md` §6 (names the API as producer of `finding.updated`), Damian's row in `.docs/STATUS.md` (closing task).
- Depends on: `api-db-schema` applied; `infra-compose` providing Redis (with AOF, ADR 0305) and MinIO.
