# api

REST API and real-time (Socket.IO) gateway between the shared database and the dashboard, and the home of the database migrations for the whole stack.

- **Owner:** Damian (module C)
- **Status:** planned, no code yet. The plan is in two OpenSpec changes: `openspec/changes/api-db-schema/` (tables and migrations, first, because the scraper and analytics need them) and `openspec/changes/api-v1/` (REST and Socket.IO).

## What it does

- Creates the shared tables (`sources`, `documents`, `findings`, `job_errors`, `calibration_points`) with Alembic, in a one-shot `api-migrate` container that runs before the other services.
- Serves the REST API of [`contracts/openapi.yaml`](../contracts/openapi.yaml) under `/api`, behind the HTTPS gateway (`https://localhost:8443/api`).
- Turns each finding's raw `score` into `risk_level` using the module thresholds the calibration panel sets.
- Relays live events (new findings, high-risk alerts, status changes, scan progress) to the dashboard over Socket.IO, namespace `/events`.

Why it is built this way: [ADR 0302](../.docs/decisions/0302-api-service.md) (separate Python service), [ADR 0303](../.docs/decisions/0303-database-schema-ownership.md) (migrations here), [ADR 0305](../.docs/decisions/0305-threshold-storage.md) (thresholds in Redis), [ADR 0306](../.docs/decisions/0306-database-driver-and-table-layout.md) (driver and tables).

## Running it

Not runnable yet. Once `api-db-schema` is applied this section will list the commands to migrate, test and start the service, and the exact SQL the scraper and analytics use to write documents and findings.
