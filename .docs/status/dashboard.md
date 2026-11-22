# Status: dashboard (Kacper)

Edit only this file for `web/` and `infra/` state. Last updated: 2026-11-22 (Sun).

## State

- Foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, hardened container.
- Data from the backend only: browser mock mode removed, MSW only in Vitest ([ADR 0206](../decisions/0206-dashboard-data-from-backend.md)); `npm run dev` needs the contract mock server or the api on `API_PROXY_TARGET` (default `http://localhost:8000`).
- Root compose with Postgres + HTTPS gateway (`infra/`).
- Recharts installed ([ADR 0203](../decisions/0203-dashboard-charts-recharts.md)) with the trend chart (`web/src/features/trend/`): hour/day switch on `GET /stats/trend`, data table as text alternative, lazy-loaded (main bundle about 122 kB gzip with socket.io-client; Recharts in a shared 105 kB chunk used by the trend and calibration sections). jsdom needs a fixed chart size or a `ResizeObserver` stub (verified).
- Findings workspace (`web/src/features/findings/`, change `findings-explorer`): filters, sort and paging of `GET /findings` kept in the URL (no router, History API), risk as text plus colour, detail side panel on `?finding=<id>` with every `fail`/`uncertain` rule and its legal basis visible, screenshot preview, and status/note change via `PATCH /findings/{id}` (not optimistic; also invalidates `stats` through `src/api/enhanced.ts`). Checked against the contract mock server at 375, 768 and 1280 px. PR #39 review fixes (`findings-explorer-review-fixes`): focus kept on sort/pager during loading and inside the modal after a save (aria-disabled save button), detail in a portal with the page inert, two-step Escape, search keeps typed spaces, `react/exhaustive-deps` enabled.
- Real-time alerts (`web/src/features/alerts/`, change `realtime-alerts`, [ADR 0208](../decisions/0208-dashboard-realtime-socketio-client.md)): one Socket.IO connection to `/events`, refetch on connect, `finding.created`/`high_risk` invalidate findings and stats, `finding.updated` patches the cached status, high-risk toasts with `Pokaż`, and a live badge in the header. Checked in headless Chrome against the mock server (dev and production build, console clean in the build).
- Calibration panel (`web/src/features/calibration/`, change `calibration-panel`): module switch, a slider over the points of `GET /calibration` with TP/FP/FN/TN, precision, recall and F1 next to their values at the current threshold, a precision/recall chart (Recharts, lazy chunk shared with the trend) with a data table, and an explicit global `Zapisz próg` (`PUT /settings/thresholds`, which also invalidates findings, stats and calibration). Demo checked on the mock: M2 0.50 to 0.90 drops "Wysokie ryzyko" from 6 to 4 and recomputes the rows.
- Web rules in `.claude/rules/web-dashboard.md`.
- Supply chain ([ADR 0209](../decisions/0209-supply-chain-scanning.md), runbook [supply-chain.md](../supply-chain.md)): decision and runbook in a docs-only PR. OSV-Scanner (offline) and Gitleaks are run by hand until the CI follow-up adds their jobs, `.gitleaks.toml` and SHA-pinned actions.
- Frontend layering ([ADR 0204](../decisions/0204-frontend-architecture.md)) applied to health, summary, findings and trend, with a lint check on components.
- `infra/per-project-image-tags` (fix for issue #63, no OpenSpec change): the four built images are tagged `investwatch/<service>:${IW_VERSION:-${COMPOSE_PROJECT_NAME:-dev}}` instead of a shared `:dev`, and the building services (`web`, `api-migrate`, `analytics`, `worker`) set `pull_policy: build`, so a plain `up` rebuilds and a failed build stops it instead of starting another checkout's or an older image. `IW_VERSION` still names a release tag. Touches `api/`, `analytics/` and `scraper/` compose files (one line each, owners asked to review). Details: `infra/README.md`, "Image tags".

## Active OpenSpec changes

- web features: none (`calibration-panel` archived, stacked on PR #40). All features from `web/CLAUDE.md` "Done" are built on the mock; next: swap in the real api once there is real data
- `agent-watch` (branch `chore/agent-watch`, archived in its PR): the `iw-watch` skill and runner for agent-to-agent hand-offs through GitHub, plus `.github/CODEOWNERS` (owners need the team's OK in review).

## Blockers and open decisions

- Compose includes the `api` service (`api/compose.yaml`), and the gateway sends `/api` and `/socket.io` to it (`infra/gateway/Caddyfile`). The `npm run dev` server still proxies to the contract mock server started by hand (see `web/README.md`) until the api has real data; switching the dev server over is Kacper's, before the demo. Team-wide entry in `.docs/STATUS.md`.
- Root `README.md` exists; its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
