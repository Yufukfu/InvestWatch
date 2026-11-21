# Status: dashboard (Kacper)

Edit only this file for `web/` and `infra/` state. Last updated: 2026-11-21 (Sat).

## State

- Foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, hardened container.
- Data from the backend only: browser mock mode removed, MSW only in Vitest ([ADR 0206](../decisions/0206-dashboard-data-from-backend.md)); `npm run dev` needs the contract mock server or the api on `API_PROXY_TARGET` (default `http://localhost:8000`).
- Root compose with Postgres + HTTPS gateway (`infra/`).
- Recharts installed ([ADR 0203](../decisions/0203-dashboard-charts-recharts.md)) with the trend chart (`web/src/features/trend/`): hour/day switch on `GET /stats/trend`, data table as text alternative, lazy-loaded (main bundle about 101 kB gzip plus a 107 kB trend chunk). jsdom needs a fixed chart size or a `ResizeObserver` stub (verified).
- Findings workspace (`web/src/features/findings/`, change `findings-explorer`): filters, sort and paging of `GET /findings` kept in the URL (no router, History API), risk as text plus colour, detail side panel on `?finding=<id>` with every `fail`/`uncertain` rule and its legal basis visible, screenshot preview, and status/note change via `PATCH /findings/{id}` (not optimistic; also invalidates `stats` through `src/api/enhanced.ts`). Checked against the contract mock server at 375, 768 and 1280 px.
- Web rules in `.claude/rules/web-dashboard.md`.
- Frontend layering ([ADR 0204](../decisions/0204-frontend-architecture.md)) applied to health, summary, findings and trend, with a lint check on components.

## Active OpenSpec changes

- none (`findings-explorer` archived, in this PR); next: Socket.IO alerts, calibration panel

## Blockers and open decisions

- Compose has no REST backend yet: the dashboard runs against `contracts/mock-server` started by hand (see `web/README.md`). Deliberate until real data exists (Kacper, Sat): the dashboard is built on the mock data and the real api is swapped in at the end, before the demo. Team-wide entry in `.docs/STATUS.md`.
- Root `README.md` exists; its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
