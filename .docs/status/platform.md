# Status: platform (Damian)

Covers `analytics/`, `api/` and `contracts/`. Edit only this file for their state. Last updated: 2026-11-21 (Sat).

## State

### contracts
- v1 in `contracts/`, required core frozen; ADRs 0301-0305 accepted (PR #3).
- Mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived).

### analytics
- `analytics-skeleton` merged (PR #10): pure pipeline, registry, M2 rules R1-R3, CLI. No worker, storage or events yet.
- Both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`.
- Proposed on its own branch, awaiting approval: `analytics-worker` (needs `main` merged in now that PR #10 is in).

### api
- `api-db-schema` applied and archived: Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack.
- In PR #15, with Kacper's review fixed in `api-db-schema-review-fixes`. `api/` lands on `main` with that PR.
- `api-v1` (REST, Socket.IO) in progress on `api/api-v1`.

### infra
- `infra-compose` (Redis and object storage) proposed on its own branch, awaiting approval.

## Active OpenSpec changes

- `api-v1` (in progress)
- `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15
- proposed, awaiting approval: `infra-compose`, `analytics-worker`

## Blockers and open decisions

- Contracts v1: the required core is frozen and accepted by Adam and Kacper ([ADR 0301](../decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is Damian's ([ADR 0303](../decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
