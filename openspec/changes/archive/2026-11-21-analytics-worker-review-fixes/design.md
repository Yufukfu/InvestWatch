# Design

## Context

PR #26 review (Kacper, 2026-11-21 19:14Z) and the coordinator's decisions on it. The archived change `2026-11-21-analytics-worker` holds the original design; this one only adjusts it.

## Decisions

1. **Detect the seed by path.** `config._DEFAULT_REGISTRY` stays the default. `config.uses_seed_registry(settings)` compares the resolved path with it, which is public and testable. The worker logs the warning once after the registry loads. Alternative: a "registry not loaded" marker on findings, which Kacper offered. Rejected for now, because it touches the Finding contract and R1 semantics; the coordinator chose the warning and honest docs.
2. **`testing.py` inside the package, not `tests/`.** The worker tests, storage tests and possible future tools import `InMemoryStore` and `NoopPublisher`. A module in the package that no production module imports keeps them out of the running service (a test asserts it) at no cost. Moving them under `tests/` would need path tricks for `conftest`. They still ship in the image as dead code, which is accepted; the review's concern was production imports.
3. **CI variables as aliases.** `TEST_DATABASE_URL` falls back to `TEST_DATABASE_ADMIN_URL`, and `TEST_REDIS_URL` falls back to `IW_TEST_REDIS_URL`. Both are explicitly test-only names that CI already sets. `REDIS_URL` and `DATABASE_URL` are deliberately not used, because they can point at a real stack.
4. **Schema drift: a one-time check now, automation later.** Applying the real Alembic migrations needs `api/`'s dependencies, which the analytics CI job does not install. Instead, the mirror and `alembic upgrade head` (run from the api image) are compared once with `pg_dump --schema-only`, limited to `sources`, `documents` and `findings`, and the result is recorded in `follow-ups.md`.

## Risks / Trade-offs

- [A test-only alias picks up an unexpected DB] → it creates and drops its own `iw_test_analytics_*` database and never touches others.
