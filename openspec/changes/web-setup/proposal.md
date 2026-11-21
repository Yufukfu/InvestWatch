## Why

The dashboard (module B) needs a runnable foundation before feature work: a React app that talks to the API only through a client generated from the shared OpenAPI contract, contract mocks so B is not blocked on `api`, and a `docker compose up` stack with the database and a single HTTPS entry point. Modules must stay independently deployable (jury criterion: architecture, 20%).

## What Changes

- `web/`: Vite + React 19 + TypeScript app, Redux Toolkit with RTK Query.
- HTTP client generated from `contracts/openapi.yaml` (`@rtk-query/codegen-openapi`). `web/scripts/sync-contracts.mjs` bundles the spec and copies the mocks into a committed snapshot under `web/src/`, so `web/` builds and deploys without the rest of the repo; `npm run contracts:check` detects drift.
- MSW serves the contract mocks in dev (`VITE_USE_MOCKS=true`); components never know whether data is mocked.
- `web/Dockerfile` (multi-stage, unprivileged nginx, read-only FS, security headers incl. strict CSP), `web/compose.yaml`.
- `infra/compose.yaml`: Postgres 17 (SCRAM auth, least-privilege app role, internal network only, no host port) and a Caddy gateway terminating TLS and routing `/api`, `/socket.io` to `api` and `/` to `web`.
- Root `compose.yaml` that only `include:`s per-module compose files; `.env.example` + `scripts/init-env.sh` generating random secrets.

## Capabilities

### New Capabilities
- `web-foundation`: dashboard app shell, generated API client, mock mode, container and gateway routing.

### Modified Capabilities
- none

## Impact

- Owner: B (`web/`, repository layout, new `infra/`). `infra/` is a new top-level directory decided by B.
- Contracts: consumes `contracts/openapi.yaml` and `contracts/mocks/` read-only; **changes no contract, route or event**.
- The integration plan names C as owner of docker-compose: the root file only includes module files, so C (and A) add their own `compose.yaml` without touching B's.
- Out of scope: dashboard features (filters, trend, alerts, calibration), Socket.IO client, Redis/MinIO, the `api` service, DB schema (Alembic, C).
