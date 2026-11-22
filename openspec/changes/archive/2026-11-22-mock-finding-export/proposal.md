## Why

Contract 1.2.0 added `GET /findings/{id}/export` (evidence pack, issue #70, PR #104), but only the real `api/` serves it. In the dashboard's mock mode the "Eksportuj" button would get a 404, so Kacper cannot build or demo the button against the mock server (follow-up of `api-finding-export`).

## What Changes

- `contracts/mock-server`: `GET /api/findings/{id}/export` with `format=json|html`, built from the same detail body as `GET /api/findings/{id}`. The pack and page code is a copy of `api/src/investwatch_api/evidence.py` (`iw_mock_server/evidence.py`), so both servers render the same page.
- The mock server has no object store, so `raw.available` is always false: `not_found` when the mock document names an `html_object_key`, `no_key` otherwise.
- The mock server's FastAPI version becomes 1.2.0. `tests/openapi_check.py` resolves file refs with a fragment, as in `api/`.

No contract change: the path is already in `contracts/openapi.yaml` 1.2.0. No mock data changes.

Owner: Damian (`contracts/`). Consumer: Kacper (`web/`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-api`: the mock server serves the finding evidence pack.

## Impact

- Code: `contracts/mock-server/src/iw_mock_server/app.py`, `contracts/mock-server/src/iw_mock_server/evidence.py` (new), tests `contracts/mock-server/tests/test_export.py` (new) and `tests/openapi_check.py`.
