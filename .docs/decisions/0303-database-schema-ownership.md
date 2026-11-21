# 0303. Ownership of the database schema and migrations

- Status: proposed
- Date: 2026-11-21
- Deciders: A, B, C (to be confirmed)

## Context

The scraper writes `sources` and `documents`, analytics writes `findings` (and later `registry_firms`, `gold_labels`, `calibration_points`), and the API reads all of them and writes statuses and settings ([integration-plan.md](../integration-plan.md) §2-§5, [analytics-plan.md](../analytics-plan.md) §3, §8). §7 of the integration plan says "Database migrations in one place (Alembic in `api`) – A and C never create tables by hand", but the `api/` service is itself undecided ([0302](0302-api-service.md)), and the scraper fetch client is still open (candidate ADR, owner A), so the scraper's language is not fixed either.

Whatever owns the schema must run before the scraper and analytics start under `docker compose up`.

## Options considered

1. **Alembic migrations in `api/`.** As written in the integration plan. Python-native, autogenerate from SQLAlchemy models. Ties every schema change to the API service and its owner; scraper and analytics depend on the API container having migrated first.
2. **Plain SQL migrations in a shared directory, applied by a one-shot compose service** (for example a `migrate` container running the files in order, or the Postgres init directory for the first version). Language-neutral, so it fits whatever the scraper ends up using; every owner can read the schema. Needs a new top-level directory (B's OK) and a simple ordering convention; no autogenerate.
3. **Each service creates and migrates the tables it writes.** No shared tooling and no cross-service dependency at start-up. Highest risk of drift between the tables and the contracts, and the API reads tables it does not control.

## Decision

_To be written by the team (A, B, C)._

## Consequences

_To be written together with the decision._
