# Status: dashboard (Kacper)

Edit only this file for `web/` and `infra/` state. Last updated: 2026-11-21 (Sat).

## State

- Foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, hardened container.
- Data from the backend only: browser mock mode removed, MSW only in Vitest ([ADR 0206](../decisions/0206-dashboard-data-from-backend.md)); `npm run dev` needs the contract mock server or the api on `API_PROXY_TARGET` (default `http://localhost:8000`).
- Root compose with Postgres + HTTPS gateway (`infra/`).
- Recharts installed ([ADR 0203](../decisions/0203-dashboard-charts-recharts.md)) with the trend chart (`web/src/features/trend/`): hour/day switch on `GET /stats/trend`, data table as text alternative, lazy-loaded (main bundle about 101 kB gzip plus a 107 kB trend chunk). jsdom needs a fixed chart size or a `ResizeObserver` stub (verified).
- Web rules in `.claude/rules/web-dashboard.md`.
- Supply chain ([ADR 0208](../decisions/0208-supply-chain-scanning.md), runbook [supply-chain.md](../supply-chain.md)): decision and runbook in a docs-only PR. OSV-Scanner (offline) and Gitleaks are run by hand until the CI follow-up adds their jobs, `.gitleaks.toml` and SHA-pinned actions.
- Frontend layering ([ADR 0204](../decisions/0204-frontend-architecture.md)) applied to health, summary, findings and trend, with a lint check on components.

## Active OpenSpec changes

- none (`web-setup`, `trend-chart`, `trend-chart-review-fixes`, `live-api-data` archived; `live-api-data` in PR #25)

## Blockers and open decisions

- Compose has no REST backend yet: the dashboard runs against `contracts/mock-server` started by hand (see `web/README.md`). Team-wide blocker in `.docs/STATUS.md`; to be solved before the demo.
- Root `README.md` exists; its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
