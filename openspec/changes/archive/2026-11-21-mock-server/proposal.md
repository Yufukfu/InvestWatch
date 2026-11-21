## Why

The dashboard (`web/`, owner Kacper) has to be built against the contract from the start, and switching to the live `api` must not need component changes ([`web/CLAUDE.md`](../../../web/CLAUDE.md)). Today Kacper only has static JSON files in `contracts/mocks/`; the real API is blocked on ADR 0302 (draft on branch `chore/c-adr-drafts`) and comes after the analytics skeleton. A mock server that speaks the real REST routes and Socket.IO events lets Kacper start now on real HTTP calls and live alerts, and later change only the base URL.

## What Changes

- New mock server in `contracts/mock-server/` (owner Damian) that serves the REST API from `contracts/openapi.yaml` under `/api`, on the same default port as the future API (`8000`), with responses built from `contracts/mocks/`.
- Read endpoints with the filters, sorting and pagination of the contract: findings list and detail, stats summary and trend, calibration per module, thresholds, sources, health, screenshot placeholder.
- In-memory state for the write endpoints: finding status change, threshold update (recomputes `risk_level`), sources add/edit, manual scan trigger.
- Socket.IO namespace `/events` emitting the contract events (`finding.created`, `finding.high_risk`, `finding.updated`, `scan.started`, `scan.finished`), including a periodic replay of mock findings so alerts can be developed without other services.
- Mock-only helper routes under `/__mock/` (reset state, trigger one event), explicitly outside the contract.
- Dockerfile and run instructions; tests that validate every response and event against the JSON Schemas.

Out of scope: the real API (ADR 0302), database and migrations (ADR 0303), `docker-compose.yml` (deployment ADR, pending), authentication, any change to the contracts themselves.

Contracts touched: none are changed. The server implements the REST routes of `contracts/openapi.yaml` and the events of `contracts/schemas/events.schema.json` ([integration-plan.md](../../../.docs/integration-plan.md) §5-§6) exactly as they are in draft v1.

Owner: Damian (`contracts/`). Consumer: Kacper (`web/`).

## Capabilities

### New Capabilities
- `mock-api`: a contract-conformant stand-in for the InvestWatch REST API and Socket.IO events, backed by the mock data in `contracts/mocks/`, for front-end development and demos without the other services.

### Modified Capabilities

None.

## Impact

- New code: `contracts/mock-server/` (Python package, tests, Dockerfile, README section). No changes to `scraper/`, `analytics/` or `web/`.
- New dependencies (scanned with `pip-audit` before merge): FastAPI, uvicorn, python-socketio; test-only: pytest, httpx, jsonschema.
- `contracts/README.md` gains a "Mock server" section; `.docs/STATUS.md` Damian row updated.
- Kacper points the dashboard at `http://localhost:8000/api` and Socket.IO at `http://localhost:8000/events`; the real API keeps the same addresses.
