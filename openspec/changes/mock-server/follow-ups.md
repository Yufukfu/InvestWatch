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
