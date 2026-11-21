# Follow-ups: mock-server

Out-of-scope or "declined to judge" items from reviews, each with one disposition (`fix-here`, `new-item`, `wont-fix`, `docs`).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review group 1 | `thresholds.json`, `trend.json`, `calibration-*.json` only checked for top-level keys | fix-here (values and point shapes validated, commit after group 2) |
| 2 | review group 1 | `pip-audit` unpinned in `requirements-dev.txt` | fix-here (pinned 2.10.1) |
| 3 | review group 1 | settings and JSON formatter untested; bad env values gave tracebacks without the variable name | fix-here (tests added, errors name the variable, negative intervals rejected) |
| 4 | review group 1 | PyYAML in runtime requirements but used only by tests | fix-here (moved to `requirements-dev.txt`) |
| 5 | review group 1 | `CONTRACTS_DIR` default via `parents[3]` wrong after a non-editable install | fix-here in group 5 (Dockerfile sets `CONTRACTS_DIR`) |
| 6 | review group 1 | `Store.reset()` replaces dicts; a component holding `store.findings` would go stale | fix-here in group 4 (replay and events always access the store through its attributes) |
| 7 | review group 1 | `summary.json` and `finding-detail.json` are not loaded | wont-fix (summary and detail are computed from the store so they reflect writes; the files remain reference examples) |
| 8 | group 2 | `openapi.yaml` `GET /findings/{id}` combines `allOf: [finding.schema.json]` (which has `additionalProperties: false`) with extra `document` and `screenshot_urls` properties, so no valid detail response can pass that schema | new-item (contract fix for the whole team; tests validate the finding and document parts separately, like `contracts/validate.py`) |
| 9 | group 2 | `starlette.testclient` deprecation warning for `httpx` | wont-fix (test-only warning; revisit when FastAPI's TestClient moves to the new client) |
| 10 | review group 2 | trend with `risk_level` is recomputed from stored findings, so its scale differs from the unfiltered mock background | docs (README mock-server section, group 5) |
| 11 | review group 2 | trend filters (`module`, `risk_level`, dates) untested | fix-here (tests added) |
| 12 | review group 2 | calibration `current_threshold` test could not fail (mock value equalled the threshold) | fix-here (test uses a store with a different threshold) |
| 13 | review group 2 | trend/calibration counts accepted floats; `labeled_samples` not required | fix-here (integers enforced, `labeled_samples` required) |
| 14 | review group 2 | `q` also searched `summary`, beyond spec and openapi | fix-here (summary dropped; spec scenario now names advertiser name and handle, as openapi does) |
| 15 | review group 2 | 404/422 bodies not checked against `components/responses` | fix-here (test helper follows response `$ref`s; 404 validated) |
| 16 | review group 2 | runtime findings must use `...Z` timestamps for trend buckets | fix-here in group 4 (replay uses `bumped_timestamp`, always UTC `Z`) |
| 17 | review group 2 | clients must URL-encode `+` in `date_from`/`date_to` | docs (README mock-server section) |
| 18 | review group 2 | CORS headers missing on unhandled 500s; `MOCK_PORT` upper bound; `nan`/`inf` intervals; partial first hour in day buckets | wont-fix (mock-only edge cases; no 500s expected, values come from the team's own `.env`) |
| 20 | group 5 | `docker build` of `contracts/mock-server/Dockerfile` not run: Docker Desktop was not running on C's machine | new-item (build once Docker is up, before the PR is merged; `python -m iw_mock_server` is covered by the smoke tests) |
| 21 | group 5 | `pip-audit -r requirements.txt -r requirements-dev.txt` (pip-audit 2.10.1, 2026-11-21) | docs (result: "No known vulnerabilities found"; for the PR body) |
| 22 | review groups 3-4 | sync routes ran in the thread pool while replay wrote the store on the loop: `dictionary changed size during iteration`, 500s under load | fix-here (all routes `async def`; stress test `test_reads_stay_consistent_while_replay_writes`) |
| 23 | review groups 3-4 | `reset()` published a half-built store; `mock_reset` ran in a thread | fix-here (dicts built first, then swapped; route async) |
| 24 | review groups 3-4 | a scan in flight wrote into the store after a reset | fix-here (`Store.generation`; the scan skips its update when it changed) |
| 25 | review groups 3-4 | replay kept running with no client connected | fix-here (replay pauses while `/events` has no clients, as the spec says) |
| 26 | review groups 3-4 | scan test did not check that `scan.started` comes before `scan.finished` | fix-here (ordered event log in the test client) |
| 27 | review groups 3-4 | `finding.created` and `finding.high_risk` are emitted from separate tasks; order likely but not guaranteed | docs (dashboard must not depend on their order; README) |
| 28 | review groups 3-4 | exceptions in spawned emit tasks go to asyncio's default log; replay task not cancelled at shutdown; replayed findings not schema-validated in tests | wont-fix (mock-only; findings are deep copies of validated mocks) |
| 29 | mutation check | the `"*"` → string conversion for Socket.IO origins was a no-op (a list with `"*"` works the same) | fix-here (conversion removed) |
| 30 | mutation check | smoke test blocked on `stdout.read()` while the server was still running | fix-here (terminate first, then read) |
| 19 | group 4 | uvicorn without `websockets` silently falls back to long-polling | fix-here (`websockets` pinned in `requirements.txt`) |
| 31 | whole-branch review | `openapi.yaml` `SourceInput` has no `required` list, but `POST /sources` must return a full `Source`; the mock requires name, platform, url, source_kind, target_modules on POST and treats PATCH as partial | new-item (contract gap for the team, together with row 8) |
| 32 | whole-branch review | README: `MOCK_HOST` missing, `.env` not loaded, relative screenshot URLs; AI log scenario count | fix-here (README and log row corrected) |
