## 1. Web app and generated client

- [x] 1.1 Test: App renders findings from contract mocks as plain text (`web/src/App.test.tsx`)
- [x] 1.2 Vite + React + TS scaffold, RTK store, `baseApi`, build-time config
- [x] 1.3 `scripts/sync-contracts.mjs` (sync + `--check`), RTK Query codegen config, generated client
- [x] 1.4 MSW handlers over the contract mocks (dev + tests), health badge, summary cards, findings table
- [x] 1.5 Tests: API-down state, scraped markup rendered as text, `contracts:check` (in sync, stale mock, stale spec, stale `generated.ts`, orphan fixture)
- [x] 1.6 Mutation check — mutations: 8 tried, 8 caught

## 2. Containers and stack

- [x] 2.1 `web/Dockerfile` (multi-stage, unprivileged nginx), `nginx.conf` + security headers, `web/compose.yaml`
- [x] 2.2 `infra/compose.yaml`: Postgres (SCRAM, app role, internal network) and Caddy HTTPS gateway
- [x] 2.3 Root `compose.yaml` (include only), `.env.example`, `scripts/init-env.sh`
- [x] 2.4 Verify `docker compose up --build`: postgres healthy, web served through https://localhost:8443 with headers

- [x] 2.5 Mutation check — mutations: n/a, config-only group (compose, nginx, Caddyfile); behaviour verified against the running stack (headers, redirect, role denies DDL, no internet from postgres)

## 3. Closing

- [x] 3.1 Apply iw-docs-update (README Quick Start, web/infra READMEs, STATUS row, security-audit) and add the iw-ai-log row
- [x] 3.2 Run iw-pr-review and fix real findings
