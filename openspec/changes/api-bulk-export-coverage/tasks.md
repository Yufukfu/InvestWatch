## 1. Contract (new paths and field, team's OK asked in the PR; the commit uses `IW_CONTRACT_CHANGE=1`)

- [ ] 1.1 `contracts/openapi.yaml`: `POST /findings/bulk-status`, `GET /findings/export`, optional `m2_coverage` in `/stats/summary`; `info.version` 1.2.0 → 1.3.0; `summary.json` regenerated with `m2_coverage`; `python contracts/validate.py` exits 0
- [ ] 1.2 Mutation check. mutations: n/a, schema only (checked by `validate.py` and by every route test that validates against it)

## 2. M2 coverage (api)

- [ ] 2.1 Tests first: matched and unmatched M2 findings, an M1 finding with a registry id, an empty database; the response validates against the contract
- [ ] 2.2 `routes/stats.py` counts `m2_coverage`
- [ ] 2.3 Mutation check

## 3. Bulk status change (api)

- [ ] 3.1 Tests first: mixed ids in order, rows and events; invalid bodies store and publish nothing; Redis down
- [ ] 3.2 `models.BulkStatus`, the PATCH update factored into one function, the route in `routes/findings.py`
- [ ] 3.3 Mutation check

## 4. Report export (api)

- [ ] 4.1 Tests first: same rows and order as the list, headers, BOM, truncation, formula prefix, invalid filter and format
- [ ] 4.2 The filter parsing of `GET /findings` as one function; `report.py` (CSV); the route
- [ ] 4.3 Mutation check

## 5. Mock server

- [ ] 5.1 Tests first: bulk change with events, export, coverage, bad bulk body; responses validate against the contract
- [ ] 5.2 The three in `iw_mock_server/app.py`; version 1.3.0
- [ ] 5.3 Mutation check

## 6. Closing

- [ ] 6.1 Docs (`iw-docs-update`): `.docs/integration-plan.md` §5, `contracts/README.md` versions, `api/README.md`, `.docs/status/platform.md`; docs-check clean; AI log entry (`iw-ai-log`)
- [ ] 6.2 PR review (`iw-pr-review`); fix real findings
