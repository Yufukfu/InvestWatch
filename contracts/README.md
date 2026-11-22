# Contracts v1

Single source of truth for data exchanged between the scraper, analytics, API and dashboard (`web/`). Background and rationale: [`.docs/integration-plan.md`](../.docs/integration-plan.md).

**Status: draft v1** – proposed by Damian, to be confirmed by Adam and Kacper (see the open decisions in the integration plan). Until confirmed, treat it as the working assumption for mocks and development.

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
docker run --rm -p 127.0.0.1:8000:8000 iw-mock-server   # loopback only: /__mock/* has no auth
```

Using it from `web/`: run the mock on port 8000, then `npm run dev` in `web/` with no `VITE_*` overrides. The app calls same-origin `/api` and `/events`, and the Vite dev server proxies `/api` and `/socket.io` to `API_PROXY_TARGET` (default `http://localhost:8000`). These are the same paths the HTTPS gateway uses, so nothing in the components changes when the real API arrives. Behind the gateway, point `API_UPSTREAM` at the mock; a mock run outside Docker must then listen on `MOCK_HOST=0.0.0.0`, because the gateway container cannot reach the host's loopback.

| What | Address on the mock itself |
|---|---|
| REST base URL | `http://localhost:8000/api` |
| Socket.IO | server path `/socket.io`, namespace `/events` |

Configuration (environment variables, all optional). The server reads only the process environment, not a `.env` file: export the variables, or use `docker run --env-file contracts/mock-server/.env` (template: `mock-server/.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `MOCK_HOST` | `127.0.0.1` (`0.0.0.0` in the Docker image) | bind address; loopback by default because `/__mock/*` has no auth |
| `MOCK_PORT` | `8000` | HTTP port |
| `MOCK_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173` | browser origins allowed for REST and Socket.IO; `*` allows any. Socket.IO also accepts same-origin (`X-Forwarded-Proto`/`Host` honoured), so the dashboard works behind the gateway without listing its origin |
| `MOCK_REPLAY_INTERVAL_S` | `10` | every N seconds a new finding (cloned from a mock one) is added and `finding.created` / `finding.high_risk` are emitted, while a client is connected; `0` disables |
| `MOCK_SCAN_DELAY_S` | `2` | seconds between `scan.started` and `scan.finished` after `POST /api/scans`; the source shows `last_run_status: running` meanwhile |
| `MOCK_MAX_ADDED` | `500` | most findings added at runtime (replay, `/__mock/emit`) kept in memory; the oldest are dropped, mock findings never (the trend loses their counts with them) |
| `CONTRACTS_DIR` | the parent `contracts/` folder | where `schemas/` and `mocks/` are read from |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout |

Behaviour worth knowing:

- Writes (`PATCH /api/findings/{id}`, `PUT /api/settings/thresholds`, `POST`/`PATCH /api/sources`, `POST /api/scans`) change an in-memory copy only. Restart or `POST /__mock/reset` restores the mocks.
- `risk_level` is computed on every read from `score` and the current thresholds, so moving the calibration slider changes the list immediately.
- `GET /api/stats/trend` without `risk_level` returns the mock background series plus findings added at runtime. With `risk_level` the series is recomputed from the findings themselves, so its scale is much smaller than the unfiltered one.
- `screenshot_urls` in a finding detail are relative (`/api/documents/…`): prefix them with the REST origin, or proxy `/api` in the dev server.
- Timestamps in query strings must be URL-encoded (`+01:00` becomes `%2B01:00`), or use the `Z` form.
- `finding.created` and `finding.high_risk` for the same finding are sent separately; do not rely on their order.
- Replay runs only while at least one client is connected to `/events`.
- Mock-only helpers, never called by the dashboard: `POST /__mock/reset` (restore data) and `POST /__mock/emit` (add one finding and emit its events now). Both need the header `X-Mock-Admin: 1` (any non-empty value), otherwise 403; the custom header forces a CORS preflight, so other web pages cannot call them: `curl -X POST -H "X-Mock-Admin: 1" http://localhost:8000/__mock/reset`.
- The server refuses to start, and names the file, if a mock does not match its schema.
- Stricter than the contract text, to stay close to what a real API would do: a blank `status` filter (`status=,`) is 422; thresholds must be JSON numbers (`true` or `"0.5"` are 422); equal sort keys are ordered by `id`; `note` is at most 10 000 characters, source `name` 500 and `schedule_cron` 200 (the contract sets no `maxLength`).

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

1. Propose the change (OpenSpec change proposal) and agree it with the whole team (contracts are shared by every module; owners in [`.github/CODEOWNERS`](../.github/CODEOWNERS)).
2. Update the schema, `openapi.yaml`, the mock generator and regenerate mocks.
3. `python contracts/validate.py` must pass.
4. Breaking changes bump the version (`v2`) in the stream message `schema` field.

## Versions

| `openapi.yaml` `info.version` | Change |
|---|---|
| 1.0.0 | v1 as frozen on Sat 14:30 (ADR 0301) |
| 1.1.0 | optional `document_id` on `GET /findings`; mocks gain one Instagram post with an M1 and an M3 finding (11 findings, 10 documents). Additive, agreed by the whole team (issue #33, OpenSpec change `findings-document-filter`) |
