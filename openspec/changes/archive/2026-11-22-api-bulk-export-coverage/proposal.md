## Why

The dashboard mockup ("Components · bulk, coverage, shortcuts, states" and the header) shows three things the API cannot serve, so the web redesign left them out (issue #115): a bulk status change for selected findings, a report export of the filtered list (`Eksportuj raport`) and an M2 coverage strip (how many M2 findings were matched to the KNF licence register).

## What Changes

- **New REST paths and a new field after the freeze (team's OK needed, version bump):** `contracts/openapi.yaml` `info.version` 1.2.0 → 1.3.0. Every change is additive: no existing path, parameter, response field or JSON Schema changes meaning.
  - `POST /findings/bulk-status`: body `{ids: [uuid, 1..200, unique], status}`, applied in one transaction. The response has one result per requested id, in request order (`updated` with the finding, or `not_found`), plus the `updated` and `not_found` counts. A `finding.updated` event is published for every updated finding after the commit, as for `PATCH /findings/{id}`.
  - `GET /findings/export`: the same filters and `sort` as `GET /findings` (no pagination) and `format=csv` (the only format). It returns a UTF-8 CSV attachment of at most 10 000 rows, with `X-Total-Count` and `X-Export-Truncated` headers. A cell that a spreadsheet would read as a formula gets a `'` prefix.
  - `GET /stats/summary` gains an optional `m2_coverage: {total, registry_matched}`: the number of M2 findings, and how many of them have `firm.registry_id` set (matched to a register entry). The existing fields are unchanged.
- `api/`: the three routes. The filter parsing of `GET /findings` moves into one function that the export reuses. The PATCH update moves into one function that the bulk route reuses.
- `contracts/mock-server`: the same three, so `web/` can build against the mock server.
- `contracts/mocks/summary.json` gains `m2_coverage` (regenerated).
- The served version becomes `1.3.0` (api and mock server).

Out of scope: the `web/` UI (Kacper builds it against the mock server), PDF export, any analytics, scraper or database schema change, and the events contract.

Owner: Damian (`contracts/`, `api/`). Consumer: Kacper (`web/`). Adam opened the issue and is asked as part of the whole team.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rest-api`: bulk status change, a CSV report export of the filtered findings list, and M2 coverage counts in the summary.
- `mock-api`: the mock server serves the same three.

## Impact

- Contract: `contracts/openapi.yaml` (two paths, one optional response field, `info.version` 1.3.0); `contracts/mocks/summary.json` and `generate_mocks.py`.
- Code: `api/src/investwatch_api/routes/findings.py`, `api/src/investwatch_api/routes/stats.py`, `api/src/investwatch_api/models.py`, `api/src/investwatch_api/report.py` (new), `api/src/investwatch_api/app.py` (version); `contracts/mock-server/src/iw_mock_server/app.py`.
- Tests: `api/tests/test_bulk_report.py` (new), `api/tests/test_resources.py` (14 paths), `contracts/mock-server/tests/test_bulk_report.py` (new).
- Team: the PR asks Kacper and Adam to approve the new paths and field. The contract commit uses `IW_CONTRACT_CHANGE=1`.
