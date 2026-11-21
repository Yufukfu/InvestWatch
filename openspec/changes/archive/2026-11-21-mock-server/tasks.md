## 1. Package, configuration and data loading

- [x] 1.1 Write failing tests: loading `contracts/mocks/` builds a store whose findings, documents, sources and events all validate against `contracts/schemas/`; a missing file or an item that fails its schema raises an error naming the file
- [x] 1.2 Create `contracts/mock-server/` with `pyproject.toml`, pinned `requirements.txt` / `requirements-dev.txt`, `.env.example` and the package skeleton
- [x] 1.3 Implement env-only settings (`MOCK_PORT`, `MOCK_CORS_ORIGINS`, `MOCK_REPLAY_INTERVAL_S`, `MOCK_SCAN_DELAY_S`, `CONTRACTS_DIR`) and the JSON logger
- [x] 1.4 Implement the loader and the in-memory store (deep copy, `reset()`), `risk_level` derivation from thresholds
- [x] 1.5 Mutation check: mutations: 15 tried, 15 caught

## 2. Read endpoints

- [x] 2.1 Write failing tests for every read path in `contracts/openapi.yaml`: status codes, response bodies validated against the referenced schemas, 404 for unknown ids, 422 for malformed ids and missing `module`
- [x] 2.2 Write failing tests for findings filters (`module`, comma-separated `status`, `platform`, `source_id`, `risk_level`, `score_min`, dates, `q`), `sort`, pagination and the empty result
- [x] 2.3 Implement `GET /api/findings` and `GET /api/findings/{id}` (finding + document + `screenshot_urls`)
- [x] 2.4 Implement `GET /api/stats/summary`, `GET /api/stats/trend`, `GET /api/calibration`, `GET /api/settings/thresholds`, `GET /api/sources`, `GET /api/health`, and the PNG placeholder for `GET /api/documents/{id}/screenshot/{viewport}`
- [x] 2.5 Add CORS for the configured origins and a test for the `Access-Control-Allow-Origin` header
- [x] 2.6 Mutation check: mutations: 24 tried, 24 caught

## 3. Write endpoints

- [x] 3.1 Write failing tests: `PATCH /api/findings/{id}` (valid status, invalid status, empty body), `PUT /api/settings/thresholds` (recomputed `risk_level` and `current_threshold`, out-of-range rejected), `POST`/`PATCH /api/sources`, `POST /api/scans` (202 and 404), `POST /__mock/reset`
- [x] 3.2 Implement the write endpoints against the in-memory store, bumping `updated_at`, and `/__mock/reset`
- [x] 3.3 Mutation check: mutations: 11 tried, 11 caught

## 4. Socket.IO events

- [x] 4.1 Write failing tests with a Socket.IO test client on `/events`: `finding.updated` after a PATCH, `scan.started` then `scan.finished` after a scan, `finding.created` (+ `finding.high_risk` when above threshold) after `POST /__mock/emit`, every payload valid against `events.schema.json`, and no events from replay when it is disabled
- [x] 4.2 Mount python-socketio with namespace `/events` next to the FastAPI app and emit events from the write endpoints
- [x] 4.3 Implement the replay background task (clone a mock finding with a new UUID and current timestamps, add it to the store, emit) and `POST /__mock/emit`; make sure a client disconnect does not stop it
- [x] 4.4 Mutation check: mutations: 15 tried, 15 caught

## 5. Packaging and run instructions

- [x] 5.1 Write a failing smoke test that starts the app with replay disabled and calls `GET /api/health`
- [x] 5.2 Add a `Dockerfile` (official pinned `python:3.13-slim` image, non-root user, only port 8000 exposed) and a `python -m` entry point
- [x] 5.3 Add the "Mock server" section to `contracts/README.md` (run locally, run in Docker, env variables, base URLs for `web/`, what `/__mock/` does)
- [x] 5.4 Run `pip-audit` on the pinned requirements and record the result for the PR body
- [x] 5.5 Mutation check: mutations: 3 tried, 3 caught (Dockerfile and README are config/docs, exempt)

## 6. Closing tasks

- [x] 6.1 Apply the iw-docs-update skill (docs, own row in `.docs/STATUS.md`, ADR drafts if any) and add the iw-ai-log row
- [x] 6.2 Run the iw-pr-review skill and fix real findings

## 7. PR #8 review follow-ups (follow-ups rows 33-42)

- [x] 7.1 Sources: `target_modules` unique, `url` stored as sent; mutations: 6 tried, 6 caught
- [x] 7.2 Settings: `LOG_LEVEL` validated, port <= 65535, finite numbers; mutations: 5 tried, 5 caught
- [x] 7.3 Scan `running` status, trend `date_from` hour, empty findings refused; mutations: 4 tried, 4 caught
- [x] 7.4 Review of 7.1-7.3: stored url must be a valid `uri`, five log levels only; mutations: 3 tried, 3 caught (scan `generation` taken in `start_scan`: mutations: n/a, the race window is not reachable in a test)
