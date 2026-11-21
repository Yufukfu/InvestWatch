# Status

Last updated: 2026-11-21 (Sat) by Damian. Update this file when a milestone moves or a blocker appears; agents read it at session start. Edit only your own module's row (limits merge conflicts); the owner of a milestone edits its row.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | contracts: required core frozen, optional fields provisional until Sat 17:00 ([ADR 0301](decisions/0301-contracts-v1.md), accepted); compose infra: Postgres + HTTPS gateway up (Kacper, PR #6), Redis and object storage proposed in `infra-compose` (Damian) |
| Sat 17:00 | Integration #1: one real document, end to end | not started |
| Sat 22:00 | Integration #2: all modules, one source each | not started |
| Sun 03:00 | Integration #3: calibration, scheduled scans | not started |
| Sun 08:00 | Feature freeze | not started |
| Sun 10:30 | Hand-in | not started |

## Modules

| Module | Owner | State | Active OpenSpec changes |
|---|---|---|---|
| scraper | Adam | SDLC merged; `scraper-v1` proposed (specs, design, tasks), not applied; ADRs 0101-0103 drafted, awaiting a human decision | `scraper-v1` (proposed) |
| dashboard | Kacper | foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, mock mode, hardened container, root compose with Postgres + HTTPS gateway (`infra/`); chart library decided: Recharts ([ADR 0203](decisions/0203-dashboard-charts-recharts.md)), dependency not installed yet; web rules in `.claude/rules/web-dashboard.md`; frontend layering decided in [ADR 0204](decisions/0204-frontend-architecture.md) (existing components still to move to it, needs an OpenSpec change) | none (`web-setup` archived) |
| analytics, api, contracts | Damian | contracts v1 in `contracts/`, core frozen; ADRs 0301-0305 accepted (PR #3); mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived); analytics: `analytics-skeleton` merged (PR #10: pure pipeline, registry, M2 rules R1-R3, CLI; no worker, storage or events yet; both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`); proposed on their own branches, awaiting approval: `infra-compose`, `api-db-schema` + `api-v1`, `analytics-worker` (needs `main` merged in now that PR #10 is in); `api/` not created on `main` | none (`analytics-skeleton` and both review-fix changes archived) |

## Blockers and open decisions

- Scraper fetch client, job queue and first social platform need a human decision: option drafts are ADRs 0101, 0102 and 0103 in `.docs/decisions/` (0103 has criteria only, no research yet). Applying `scraper-v1` task groups 3 and 6 waits on 0101 and 0102.
- Open with Damian before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`) and who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is Kacper's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials). `api/` from the integration plan does not exist yet; Damian creates it with a `CLAUDE.md` when needed.
- Contracts v1 (Damian): the required core is frozen and accepted by Adam and Kacper ([ADR 0301](decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Alembic migrations live in `api/` ([ADR 0303](decisions/0303-database-schema-ownership.md)), so the `documents` index, `job_errors` and published-marker migration is Damian's; it waits for `api/` to exist.
- Social media: one platform first; which one is open.
- Root `README.md` exists (Kacper); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
