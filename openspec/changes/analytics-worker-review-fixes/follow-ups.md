# Follow-ups

Kacper's review of PR #26 (225e9cf, 2026-11-21 19:14Z), each item with the coordinator's decision. One disposition each.

| # | Review item | Finding | Disposition |
|---|---|---|---|
| 1 | Required 1 | The shipped container judges every real firm against 3 fictional firms (`registry/seed.csv`), so real-firm R1 results and high-risk alerts are wrong. | docs + fix-here: README, `.env.example`, compose comment and `.docs/status/platform.md` say so; the worker logs a `registry_seed` WARNING at startup. R1 semantics unchanged. **new-item:** a real KNF registry loader (`.docs/analytics-plan.md` §3: the five KNF lists, `seed.csv` fallback) |
| 2 | Required 2 | `.docs/analytics-plan.md` §4 promised URL-level dedup. | fixed: re-analysis of the same document updates its finding, a changed page is a new document with a new finding (`(document_id, module)`). **new-item:** URL-level grouping of findings in the API or UI |
| 3 | Required 3 | `.docs/security-audit.md` had no worker entry. | fixed: "Service notes / analytics worker" (credentials, networks, `/health`, `MAX_DOCUMENT_BYTES`) and a fresh `pip-audit` row |
| 4 | Smaller 4 | Stale "proposed, awaiting approval" line in `.docs/status/platform.md`. | fixed |
| 5 | Smaller 5 | The worker joined `egress` with no outbound call. | fixed: `data` only; `analytics-llm-p0` adds `egress` with the LLM client. Empty `LLM_*` slots kept |
| 6a | Smaller 6 | A finding that crosses the threshold on re-analysis publishes nothing (events fire only for new findings). | **new-item:** publish `finding.high_risk` (or `finding.updated`) when an update crosses the threshold; needs a product decision on duplicate alerts |
| 6b | Smaller 6 | A clean page is stored and announced at score 0 with "brak naruszeń w sprawdzonych regułach" although only R1-R3 run. | fixed for the title: it names the checked rules ("brak naruszeń w regułach R1, R2, R3"); the summary already lists them and says the other UKNF rules are not checked yet. **new-item:** whether clean pages should create findings (and `finding.created`) at all |
| 7 | Smaller 7 | Postgres tests ran on a hand-copied `tests/sql/schema.sql` and skipped without `TEST_DATABASE_URL`, so CI never ran them. | fixed-here: the tests also read CI's `TEST_DATABASE_ADMIN_URL` and `IW_TEST_REDIS_URL` (398 passed, 0 skipped with only those set). The mirror was compared with `alembic upgrade head` (api image) by `pg_dump --schema-only` of `sources`, `documents`, `findings`: identical once the mirror took the real double-prefixed CHECK names, which it now uses. **new-item:** an automated drift check in CI (needs `api/` dependencies in the analytics job) |
| 8 | Smaller 8 | `InMemoryStore` and `NoopPublisher` in the production modules; `worker.main` duplicated `Settings.from_env` and imported the private `_DEFAULT_REGISTRY`. | fixed: both moved to `investwatch_analytics/testing.py`, which the worker never imports (tested); `Settings.from_env(env)` takes a mapping and `main` uses it |
| 9 | Smaller 9 | No final `pip-audit` record; no `.docs/INDEX.md` row for operating the worker. | fixed: `.docs/security-audit.md` row, INDEX router row |
