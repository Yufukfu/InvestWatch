## 1. Contract (new paths and field, team's OK asked in the PR; the commit uses `IW_CONTRACT_CHANGE=1`)

- [x] 1.1 `contracts/openapi.yaml`: `POST /findings/bulk-status`, `GET /findings/export`, optional `m2_coverage` in `/stats/summary`; `info.version` 1.2.0 → 1.3.0; `summary.json` regenerated with `m2_coverage`; `python contracts/validate.py` exits 0
- [x] 1.2 Mutation check. mutations: n/a, schema only (checked by `validate.py` and by every route test that validates against it)

## 2. M2 coverage (api)

- [x] 2.1 Tests first: matched and unmatched M2 findings, an M1 finding with a registry id, an empty database; the response validates against the contract
- [x] 2.2 `routes/stats.py` counts `m2_coverage`
- [x] 2.3 Mutation check. mutations: 3 tried, 3 caught (no `astext`, no M2 filter, mock: any firm counts as matched, caught after a test on edited mock data)

## 3. Bulk status change (api)

- [x] 3.1 Tests first: mixed ids in order, rows and events; invalid bodies store and publish nothing; Redis down
- [x] 3.2 `models.BulkStatus`, the PATCH update factored into one function, the route in `routes/findings.py`
- [x] 3.3 Mutation check. mutations: 5 tried, 4 caught (no uniqueness check, 1000 ids allowed, events for not-found ids, mock: no events); the microsecond bump of `updated_at` is PATCH's existing logic, reused, and not reachable with these fixtures

## 4. Report export (api)

- [x] 4.1 Tests first: same rows and order as the list, headers, BOM, truncation, formula prefix, invalid filter and format
- [x] 4.2 The filter parsing of `GET /findings` as one function; `report.py` (CSV); the route
- [x] 4.3 Mutation check. mutations: 8 tried, 8 caught (no formula prefix, no tab/CR prefix (caught after adding a test), all rules as failed, no BOM, truncation flag always false, sort ignored, mock: reversed rows, wrong total)

## 5. Mock server

- [x] 5.1 Tests first: bulk change with events, export, coverage, bad bulk body; responses validate against the contract
- [x] 5.2 The three in `iw_mock_server/app.py`; version 1.3.0
- [x] 5.3 Mutation check. mutations: counted with groups 2-4 (mock mutants)

## 6. Closing

- [x] 6.1 Docs (`iw-docs-update`): `.docs/integration-plan.md` §5, `contracts/README.md` versions, `api/README.md`, `.docs/status/platform.md`; docs-check clean; AI log entry (`iw-ai-log`)
- [x] 6.2 PR review (`iw-pr-review`); fix real findings
