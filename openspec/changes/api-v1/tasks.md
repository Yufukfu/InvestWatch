# Tasks

Starts after change `api-db-schema` groups 1-3 (package, tables, migrate service). Groups 1-4 are the Integration #1 path (findings, PATCH, thresholds, relay, health); groups 5-6 are needed by Integration #2.

## 1. App skeleton, errors and health

- [x] 1.1 Failing tests: `GET /api/health` scenarios "All up", "MinIO down" and "Postgres down", and "Malformed path id" (422 in the `{error, details}` shape)
- [x] 1.2 Add pinned `fastapi`, `uvicorn[standard]`, `python-socketio`, `redis`, `minio`, `jsonschema[format]` (dev: `httpx`, `pyyaml`; no `fakeredis`: Redis tests use a real Redis from `TEST_REDIS_URL` and skip without it); `create_app()` with the copied exception handlers, async engine, Redis client, `ObjectStore` interface over MinIO, and `/api/health`; the 1.1 tests pass
- [x] 1.3 Copy `openapi_check.py` from the mock server branch into `api/tests/` and seed fixtures from `contracts/mocks/` through `api-db-schema`'s mapping; the test that every path in `contracts/openapi.yaml` has a route (11 paths) lands with group 5, when the last routes exist
- [x] 1.4 Mutation check (iw-commit-cycle step 3); mutations: 3 tried, 3 caught (committed together with group 2: both build on the app factory)

## 2. Thresholds and risk level

- [x] 2.1 Failing tests for every "Thresholds setting" scenario and "Boundaries with threshold 0.5"
- [x] 2.2 Threshold store (JSON string at `iw:settings:thresholds`, defaults written when missing, last-known fallback) and the SQL `CASE` for `risk_level`; `GET`/`PUT /api/settings/thresholds`; the 2.1 tests and "Redis unavailable" pass
- [x] 2.3 Mutation check; mutations: 6 tried, 6 caught

## 3. Findings: list, detail, PATCH

- [x] 3.1 Failing tests for "Findings list filters, sort and pagination", "Filter uses the same rule" (list part) and "Threshold change applies at once"
- [x] 3.2 `GET /api/findings` query with all filters, literal `q`, sort tie-breakers and pagination; the 3.1 tests pass
- [x] 3.3 Failing tests, then `GET /api/findings/{id}` with `document` and `screenshot_urls`: "Document with two screenshots", "Document without screenshots", "Unknown finding" pass (finding and document parts validated separately, design open question 1)
- [x] 3.4 Failing tests, then `PATCH /api/findings/{id}` with the copied `FindingPatch`, `updated_at` bump and `finding.updated` published after commit: every "Status and note changes" scenario passes
- [x] 3.5 Mutation check; mutations: 13 tried, 13 caught (one survivor first: the `updated_at` test compared strings; now compares times)

## 4. Event relay

- [x] 4.1 Failing tests with `socketio.AsyncClient` against uvicorn on a free port: "Finding created", "High-risk alert passes through", "Scan progress", "Not JSON", "Unknown type", "Payload not matching its type", "Status change reaches another tab"
- [x] 4.2 `socketio.AsyncServer` on `/events` wrapped around the FastAPI app, Pub/Sub subscriber with schema validation from `CONTRACTS_DIR`, `CORS_ORIGINS`; the 4.1 tests pass
- [x] 4.3 Failing tests, then reconnect with capped backoff and the health flag (outages simulated by a TCP proxy in front of the test Redis that drops every connection and refuses new ones): "Redis restarts", "Redis down at start-up", "No client connected", "Foreign origin rejected" pass
- [x] 4.4 Mutation check; mutations: 6 tried, 6 caught; review fixes: mutations: 1 tried, 1 caught

## 5. Stats, calibration, sources, scans, screenshots

- [x] 5.1 Failing tests, then `/api/stats/summary` and `/api/stats/trend` with zero-filled buckets and the default ranges of design decision 9: every "Statistics" scenario and the stats part of "Filter uses the same rule" pass
- [x] 5.2 Failing tests, then `/api/calibration` from the latest `calibration_points` run: every "Calibration curve" scenario passes
- [x] 5.3 Failing tests, then `GET`/`POST /api/sources` and `PATCH /api/sources/{id}` with the copied models: every "Sources management" scenario passes
- [x] 5.4 Failing tests, then `POST /api/scans` (`XADD iw:scan-requests`): every "Manual scan request" scenario passes and the stream entry validates against `scan_request`
- [x] 5.5 Failing tests, then the screenshot route over `ObjectStore`: every "Screenshot proxy" scenario passes, including that the key comes only from the document row
- [x] 5.6 Mutation check; mutations: 17 tried, 16 caught, 1 equivalent (a redundant 404 guard in `PATCH /sources`, removed); plus the 11-path route test from task 1.3

## 6. Container and end to end

- [ ] 6.1 Add the `api` service to `api/compose.yaml` (uvicorn on 8000, `iw-edge` + `iw-data`, `depends_on` `api-migrate` completed and Postgres/Redis healthy, read-only filesystem, `no-new-privileges`, resource limits, MinIO variable names agreed with `infra-compose`); `docker compose up --build` starts it healthy
- [ ] 6.2 Failing end-to-end check, then fix what it shows: through `https://localhost:8443`, a document inserted by hand and a finding upserted with the `api-db-schema` SQL appear in `GET /api/findings`, a published `finding.created` reaches a Socket.IO client on `/events` ("Same-origin connection"), and a `PATCH` is seen by a second client; output pasted in the PR body
- [ ] 6.3 Mutation check; line reads `mutations: n/a, end-to-end check only` unless code changed in 6.2

## 7. Closing

- [ ] 7.1 Apply the `iw-docs-update` skill (`api/CLAUDE.md`, `api/README.md` with the edge-rule assumptions of design decision 9, `.docs/integration-plan.md` §6 naming the API as producer of `finding.updated`, Damian's row in `.docs/STATUS.md`), run docs-check, run `pip-audit` on `api/requirements*.txt` and record it in `.docs/security-audit.md`, and add the `iw-ai-log` row
- [ ] 7.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
