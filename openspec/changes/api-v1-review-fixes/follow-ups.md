# Follow-ups: api-v1-review-fixes

Items from Kacper's review of PR #21 (at 8caa046) that this change does not close, and what the fixes turned up. One disposition each (`fix-here`, `new-item`, `wont-fix`, `docs`).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review item 2, 13 | PR #21 needs #18's Redis, MinIO and `.env` entries; `main`'s root compose already includes `api/compose.yaml` | fix-here (this branch merges `chore/infra-compose-v2`; PR #21 is stacked on #18 and merges after it) |
| 2 | review item 6 | nothing consumes `iw:scan-requests`: `POST /scans` queues, no scan runs | new-item (scraper, Adam: consumer group on `iw:scan-requests` and the `scan.*` events; `.docs/integration-plan.md` §5 says so; `openspec/changes/scraper-v1/` not edited here, Damian raises it with Adam) |
| 3 | review item 11 | CI cannot run the api tests (no `httpx`, no Postgres or Redis service; DB tests skip) | new-item (CI services); conformance is verified locally: suite on Postgres 17 + Redis 8 and the end-to-end run through the gateway, listed in the PR body |
| 4 | review item 12 | the trend default window (24 hours for `hour`, 14 days for `day`) is not in the OpenAPI text | docs (`api/README.md`; `contracts/openapi.yaml` is frozen, add it with the next contract version) |
| 5 | review item 12 | SQL statements live in the route modules, `queries/__init__.py` said "one module per resource" | fix-here (docstring describes the real layout; moving the statements is not worth the churn now) |
| 6 | review item 9 | the archived mock server normalised source URLs (`HttpUrl`); the API now stores them as sent | docs (README; the dashboard sends what the user typed, so as-sent is what it shows back) |
| 7 | full-suite run | `test_default_list_query_uses_an_index` (from `api-db-schema-review-fixes`) failed once in a full run and passes alone (planner choice on a freshly analysed table) | new-item (make the plan test deterministic, e.g. `SET enable_sort = off` or more rows) |
| 8 | mutation check group 2 | reading the stored calibration run even when labels exist is an equivalent mutant | wont-fix (one extra query, same response) |
