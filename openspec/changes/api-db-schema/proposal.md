# Proposal

## Why

Nothing in the stack has tables yet. The scraper cannot insert documents (`scraper-v1` task 1.4 and group 5 wait on the unique index, `job_errors` and the published marker), and analytics cannot store findings. Integration #1 (Sat 17:00) needs both. [ADR 0303](../../../.docs/decisions/0303-database-schema-ownership.md) puts every migration in Alembic under `api/`, and `api/` does not exist yet. This change creates the smallest `api/` package that can own and run those migrations, so the REST and Socket.IO work (change `api-v1`) is not on the critical path for the schema.

## What Changes

- Create the `api/` service directory with `CLAUDE.md` (first, as the root `CLAUDE.md` requires), `README.md`, a Python package `investwatch_api` with pinned dependencies, and Alembic configuration under `api/migrations/`.
- Add SQLAlchemy 2 table definitions and an initial Alembic revision for the shared tables: `sources`, `documents`, `findings`, `job_errors`, `calibration_points`. Layout and driver are recorded in a new ADR 0307.
- `documents`: contract scalar fields as columns plus `payload JSONB` for the rest, a unique index on `(source_id, content_hash)` for deduplication, and a `stream_published_at` marker for "published to `iw:documents`" with an index for the republish sweep.
- `findings`: filterable fields as columns plus JSONB for `firm`, `advertiser`, `rules`, `model`; unique on `(document_id, module)` so a re-scan of the same document updates the finding instead of adding a duplicate. `risk_level` is not stored ([ADR 0305](../../../.docs/decisions/0305-threshold-storage.md)).
- Add `api/compose.yaml` with a one-shot `api-migrate` service that runs `alembic upgrade head` as `iw_admin`, so scraper and analytics can wait for it. Adding it to the root `include:` is coordinated with the `infra-compose` change (the root file is not edited here).
- Add `api` to the services table in the root `CLAUDE.md` and a row in `.docs/INDEX.md` (`.docs/INDEX.md` rules for a new service directory).
- Owner: Damian (module C, `api/`).
- Out of scope: every REST route and Socket.IO (change `api-v1`), `registry_firms` and `gold_labels` (added by the analytics changes that need them, as later Alembic revisions here), the Postgres and Redis containers themselves (`infra/`, change `infra-compose`), any writer code in the scraper or analytics.

## Contracts

- Touches no contract, REST route or event. The tables store `ScrapedDocument`, `Finding` and `Source` v1 ([integration-plan.md](../../../.docs/integration-plan.md) §3-§4) without changing their shape. Every column and CHECK constraint takes its allowed values from `contracts/schemas/`.
- Fixes the database side of integration points 1 and 4 (§2): the dedup rule the scraper relies on and the upsert key analytics relies on.

## Capabilities

### New Capabilities
- `database-schema`: the shared Postgres tables, their constraints and indexes, and the migration step every other service waits for.

### Modified Capabilities

## Impact

- New directory `api/` (approved by ADR 0302, which names `api/` and its `CLAUDE.md`; Kacper owns the layout and is told in the PR).
- Dependencies (pinned, `pip-audit` before merge): `sqlalchemy`, `alembic`, `psycopg[binary]`; tests use `pytest` against a real Postgres 17 from `infra/compose.yaml`.
- Unblocks `scraper-v1` group 5 (Adam) and the storage step of `analytics-worker` (Damian). Both must use the column names and the conflict rules in `specs/database-schema/spec.md`.
- Docs: `api/CLAUDE.md`, `api/README.md`, ADR 0307, `.docs/decisions/README.md`, root `CLAUDE.md` services table, `.docs/INDEX.md`, Damian's row in `.docs/STATUS.md` (closing task).
