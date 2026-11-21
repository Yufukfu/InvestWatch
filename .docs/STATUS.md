# Status

Last updated: 2026-11-21 (Sat) by Damian. Update this file when a milestone moves or a blocker appears; agents read it at session start. Edit only your own module's row (limits merge conflicts); the owner of a milestone edits its row.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | in progress (C) |
| Sat 17:00 | Integration #1: one real document, end to end | not started |
| Sat 22:00 | Integration #2: all modules, one source each | not started |
| Sun 03:00 | Integration #3: calibration, scheduled scans | not started |
| Sun 08:00 | Feature freeze | not started |
| Sun 10:30 | Hand-in | not started |

## Modules

| Module | Owner | State | Active OpenSpec changes |
|---|---|---|---|
| scraper | A | SDLC merged; `scraper-v1` proposed (specs, design, tasks), not applied; ADRs 0101-0103 drafted, awaiting a human decision | `scraper-v1` (proposed) |
| dashboard | B | foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, mock mode, hardened container, root compose with Postgres + HTTPS gateway (`infra/`); Recharts installed ([ADR 0203](decisions/0203-dashboard-charts-recharts.md)) with the trend chart (`web/src/features/trend/`, hour/day switch on `GET /stats/trend`; production bundle 98 kB to 206 kB gzip; jsdom needs a fixed chart size or a `ResizeObserver` stub, verified); web rules in `.claude/rules/web-dashboard.md`; frontend layering decided in [ADR 0204](decisions/0204-frontend-architecture.md) (existing components still to move to it, needs an OpenSpec change) | `trend-chart` (applied, in review; `web-setup` archived) |
| analytics, api, contracts | Damian | plans written; contracts v1 in `contracts/`; ADRs 0301-0305, see `.docs/decisions/README.md`; mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) in review | `mock-server` (branch `contracts/mock-server`) |

## Blockers and open decisions

- Scraper fetch client, job queue and first social platform need a human decision: option drafts are ADRs 0101, 0102 and 0103 in `.docs/decisions/` (0103 has criteria only, no research yet). Applying `scraper-v1` task groups 3 and 6 waits on 0101 and 0102.
- Open with C before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`) and who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is B's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials). `api/` from the integration plan does not exist yet; C creates it with a `CLAUDE.md` when needed.
- Contracts v1 exist as a draft in `contracts/` (C) and are still to be confirmed by A and B; rendering metadata (`blocks`, screenshots) still to be discussed with A.
- Social media: one platform first; which one is open.
- Root `README.md` exists (B); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
