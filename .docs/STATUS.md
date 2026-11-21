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
| scraper | Adam | `scraper-v1` (fetch, parse, politeness, guards) implemented and reviewed, in PR; `scraper-ingest` (database sink, `documents`, `iw:documents`) and `scraper-orchestration` (queue, schedule, scan requests, the run that joins the pieces) not started; ADRs 0101 and 0102 accepted on merge, 0103 criteria only | none (`scraper-v1` archived) |
| dashboard | Kacper | foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, mock mode, hardened container, root compose with Postgres + HTTPS gateway (`infra/`); chart library decided: Recharts ([ADR 0203](decisions/0203-dashboard-charts-recharts.md)), dependency not installed yet; web rules in `.claude/rules/web-dashboard.md`; frontend layering ([ADR 0204](decisions/0204-frontend-architecture.md)) applied to health, summary and findings, with a lint check on components | none (`web-setup` archived) |
| analytics, api, contracts | Damian | contracts v1 in `contracts/`, core frozen; ADRs 0301-0305 accepted (PR #3); mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived); analytics: `analytics-skeleton` merged (PR #10: pure pipeline, registry, M2 rules R1-R3, CLI; no worker, storage or events yet; both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`); proposed on their own branches, awaiting approval: `infra-compose`, `api-db-schema` + `api-v1`, `analytics-worker` (needs `main` merged in now that PR #10 is in); `api/` not created on `main` | none (`analytics-skeleton` and both review-fix changes archived) |

## Blockers and open decisions

- ADRs 0101 (fetch client) and 0102 (job queue) are written and take effect when the `scraper-v1` PR merges; the first social platform (0103, criteria only) is decided in `scraper-v2`.
- Open with Damian, for `scraper-ingest`: who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet). `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is Kacper's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials). `api/` from the integration plan does not exist yet; Damian creates it with a `CLAUDE.md` when needed.
- Contracts v1 (Damian): the required core is frozen and accepted by Adam and Kacper ([ADR 0301](decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Alembic migrations live in `api/` ([ADR 0303](decisions/0303-database-schema-ownership.md)), so the `documents` index, `job_errors` and published-marker migration is Damian's; it waits for `api/` to exist.
- Social media: one platform first; which one is open.
- Root `README.md` exists (Kacper); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
