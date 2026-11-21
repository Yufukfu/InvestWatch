# Contracts v1

Single source of truth for data exchanged between the scraper, analytics, API and dashboard (`web/`). Background and rationale: [`.docs/integration-plan.md`](../.docs/integration-plan.md).

**Status: draft v1** – proposed by C, to be confirmed by A and B (see the open decisions in the integration plan). Until confirmed, treat it as the working assumption for mocks and development.

| File | Used by | Describes |
|---|---|---|
| `schemas/scraped-document.schema.json` | scraper → analytics, API | a collected document (`documents` table) |
| `schemas/finding.schema.json` | analytics → API → dashboard | an analysis result (`findings` table) |
| `schemas/source.schema.json` | scraper, API, dashboard | a scraping source (`sources` table) |
| `schemas/events.schema.json` | all | Redis Stream messages and Socket.IO events |
| `openapi.yaml` | API ↔ dashboard | REST endpoints (OpenAPI 3.1, references the schemas above) |
| `mocks/*.json` | dashboard, tests | example responses for every endpoint and event |

## Mock data

All firms, people, handles and URLs in the mocks are **fictional**. Mock file ↔ endpoint:

| Mock | Endpoint / channel |
|---|---|
| `findings.json` | `GET /api/findings` |
| `finding-detail.json` | `GET /api/findings/{id}` |
| `summary.json` | `GET /api/stats/summary` |
| `trend.json` | `GET /api/stats/trend` |
| `calibration-M1.json`, `-M2`, `-M3` | `GET /api/calibration?module=…` |
| `thresholds.json` | `GET /api/settings/thresholds` |
| `sources.json` | `GET /api/sources` |
| `health.json` | `GET /api/health` |
| `events.json` | Socket.IO `/events` (sequence of events) |
| `documents.json` | rows of the `documents` table (scraper output) |

Regenerate after changing a scenario: `python contracts/mocks/generate_mocks.py` (deterministic – same UUIDs every run).

## Mock server

`mock-server/` serves the REST API from `openapi.yaml` and the Socket.IO events from `events.schema.json`, backed by the mocks above, so the dashboard can work against real HTTP and WebSocket calls before the real API exists. It uses the same addresses as the planned API, so switching later means changing nothing but the base URL. It is a development and demo tool, not the real API.

Run locally (Python 3.13+):

```
pip install -r contracts/mock-server/requirements.txt
cd contracts/mock-server/src
python -m iw_mock_server
```

Run in Docker (build context is `contracts/`):

```
docker build -f contracts/mock-server/Dockerfile -t iw-mock-server contracts
docker run --rm -p 8000:8000 iw-mock-server
```

Addresses for `web/`:

| What | Address |
|---|---|
| REST base URL | `http://localhost:8000/api` |
| Socket.IO | `io("http://localhost:8000/events")` (server path `/socket.io`, namespace `/events`) |

Configuration (environment variables, all optional; see `mock-server/.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `MOCK_PORT` | `8000` | HTTP port |
| `MOCK_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173` | browser origins allowed for REST and Socket.IO; `*` allows any |
| `MOCK_REPLAY_INTERVAL_S` | `10` | every N seconds a new finding (cloned from a mock one) is added and `finding.created` / `finding.high_risk` are emitted, while a client is connected; `0` disables |
| `MOCK_SCAN_DELAY_S` | `2` | seconds between `scan.started` and `scan.finished` after `POST /api/scans` |
| `CONTRACTS_DIR` | the parent `contracts/` folder | where `schemas/` and `mocks/` are read from |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout |

Behaviour worth knowing:

- Writes (`PATCH /api/findings/{id}`, `PUT /api/settings/thresholds`, `POST`/`PATCH /api/sources`, `POST /api/scans`) change an in-memory copy only. Restart or `POST /__mock/reset` restores the mocks.
- `risk_level` is computed on every read from `score` and the current thresholds, so moving the calibration slider changes the list immediately.
- `GET /api/stats/trend` without `risk_level` returns the mock background series plus findings added at runtime. With `risk_level` the series is recomputed from the findings themselves, so its scale is much smaller than the unfiltered one.
- Timestamps in query strings must be URL-encoded (`+01:00` becomes `%2B01:00`), or use the `Z` form.
- Mock-only helpers, never called by the dashboard: `POST /__mock/reset` (restore data) and `POST /__mock/emit` (add one finding and emit its events now).
- The server refuses to start, and names the file, if a mock does not match its schema.

Tests: `pip install -r contracts/mock-server/requirements-dev.txt`, then `pytest` in `contracts/mock-server/`.

## Validation

```
pip install -r contracts/requirements.txt
python contracts/validate.py                  # all mocks + referential integrity + OpenAPI parse
python contracts/validate.py document out.json   # check scraper output against the contract
python contracts/validate.py finding out.json    # check analytics output against the contract
```

Run it before merging any change to `contracts/`.

## Changing a contract

1. Propose the change (OpenSpec change proposal) and agree it with the affected owners (A, B, C).
2. Update the schema, `openapi.yaml`, the mock generator and regenerate mocks.
3. `python contracts/validate.py` must pass.
4. Breaking changes bump the version (`v2`) in the stream message `schema` field.
