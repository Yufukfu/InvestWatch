## 1. Mock export route

- [x] 1.1 Tests first (`contracts/mock-server/tests/test_export.py`): every mock finding exports a contract-valid pack equal to its detail, with only failed rules and `raw` unavailable (`not_found` / `no_key`); the HTML page with its CSP; 404 in both formats; 422 for a bad id or format; hostile text escaped
- [x] 1.2 `iw_mock_server/evidence.py` copied from `api/`, the route in `app.py` sharing `finding_detail` with `GET /api/findings/{id}`; version 1.2.0; `tests/openapi_check.py` resolves fragment refs
- [x] 1.3 Mutation check (iw-commit-cycle step 3), on the mutants chosen by the agent only. mutations: 3 tried, 3 caught (format branches swapped; CSP headers dropped; pack built without the document)

## 2. Closing

- [x] 2.1 Docs (`iw-docs-update`): `contracts/README.md` route table, `.docs/status/platform.md`; docs-check clean
- [x] 2.2 AI log entry (`iw-ai-log`)
- [x] 2.3 PR review (`iw-pr-review`)
