## Why

Analytics stage 2 (M1 + M3) can raise more than one finding for the same document; findings are unique per `(document_id, module)` (issue #33). The dashboard's detail panel should list every finding of the open document, but `GET /findings` cannot filter by document, so the panel only sees the current page: with sort by score or date the M1 and M3 of one post can land on different pages. The mocks have no document with two findings either, so the mock server has nothing to demo. Kacper asked for both on issue #33 (2026-11-21).

## What Changes

- **Contract change after the freeze (whole team's OK needed, version bump):** `contracts/openapi.yaml` gets an optional query parameter `document_id` (UUID) on `GET /findings`, and `info.version` goes from `1.0.0` to `1.1.0`. Additive and optional: a request without it behaves exactly as today. No schema in `contracts/schemas/` changes.
- `contracts/mocks/generate_mocks.py` learns scenarios with several findings and gains one Instagram post with an M1 finding (finfluencer with an affiliate code for a registered firm) and an M3 finding (paid buy/sell signals) on the same document. The mocks are regenerated: 10 documents, 11 findings.
- `api/`: `GET /api/findings?document_id=` filters on `findings.document_id`, combined (AND) with every other filter, sort and pagination. Served version becomes `1.1.0`.
- `contracts/mock-server`: the same parameter on its `GET /api/findings`.
- Docs: `.docs/integration-plan.md` §5 lists the filter; `contracts/README.md` records the 1.1.0 bump.

Out of scope: `web/` (Kacper adds `document_id`/URL to the rows and the "other findings for this document" section, and re-syncs his contract snapshot `web/src/api/openapi.json` and `web/src/test/fixtures/`), a `GET /documents/{id}/findings` route, and any change to how analytics writes findings.

Owner: Damian (`contracts/`, `api/`). Consumer: Kacper (`web/`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rest-api`: `GET /api/findings` accepts `document_id` and returns only that document's findings, combined with the other filters and pagination.
- `mock-api`: the mock server's `GET /api/findings` honours `document_id` the same way, and its mocks include a document with an M1 and an M3 finding.

## Impact

- Contract: `contracts/openapi.yaml` (`GET /findings` parameter, `info.version` 1.1.0), `contracts/mocks/*.json` (regenerated). REST route touched: `GET /findings`. No event, no JSON Schema, no database change (the unique index `uq_findings_document_module` already leads with `document_id`).
- Code: `api/src/investwatch_api/routes/findings.py`, `api/src/investwatch_api/app.py` (version), `contracts/mock-server/src/iw_mock_server/app.py`, `contracts/mocks/generate_mocks.py`, and their tests (mock counts 9 → 11 findings, 9 → 10 documents).
- Team: needs Adam's and Kacper's OK before the contract files are committed (`IW_CONTRACT_CHANGE=1`, reported in the PR body).
