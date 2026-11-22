## 1. Contract (new path, team's OK asked in the PR; the commit uses `IW_CONTRACT_CHANGE=1`)

- [x] 1.1 `contracts/openapi.yaml`: `GET /findings/{id}/export` with `format` (`json`|`html`), the JSON pack schema, `text/html`, 404 and 422; `info.version` 1.1.0 → 1.2.0; `python contracts/validate.py` exits 0
- [x] 1.2 `api/tests/openapi_check.py` resolves `./schemas/x.schema.json#/$defs/...`; `test_resources.py` counts 12 paths
- [x] 1.3 Mutation check (iw-commit-cycle step 3). mutations: 1 tried, 1 caught (fragment dropped from rewritten refs)

## 2. Export route

- [x] 2.1 Tests first (`api/tests/test_export.py`, real Postgres and Redis): JSON pack validates against the contract and holds URL, `content_hash`, `fetched_at`, text, raw HTML with SHA-256, screenshot URLs, failed rules with legal basis and quote, scores and model; equals the detail; 404 for an unknown id in both formats; 422 for a bad id or format; no key, missing object, store down, truncation over 2 MB; HTML page content, headers and escaping of hostile text, titles, URLs and viewport keys
- [x] 2.2 `evidence.py` (pack and page) and the route in `routes/findings.py`; the detail body moves into `finding_detail` unchanged; `app.py` version 1.2.0
- [x] 2.3 Mutation check (iw-commit-cycle step 3), on the mutants chosen by the agent only. mutations: 5 tried, 5 caught (failed-rule filter `!= pass`, caught after adding `uncertain` and `not_applicable` rules to the fixture; no escaping; `javascript:` links; hash over the truncated bytes; store error not caught)

## 3. Closing

- [x] 3.1 Docs (`iw-docs-update`): `.docs/integration-plan.md` §5, `contracts/README.md` versions, `api/README.md`, `.docs/status/platform.md`; docs-check clean
- [x] 3.2 AI log row (`iw-ai-log`)
- [x] 3.3 PR review (`iw-pr-review`)
