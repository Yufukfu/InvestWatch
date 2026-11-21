# Status

Last updated: 2026-11-21 (Sat) by Damian. Update this file when a milestone moves or a blocker appears; agents read it at session start. Edit only your own module's row (limits merge conflicts); the owner of a milestone edits its row.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | contracts: required core frozen, optional fields provisional until Sat 17:00 ([ADR 0301](decisions/0301-contracts-v1.md), accepted); compose infra: Postgres + HTTPS gateway up (B, PR #6), Redis and object storage proposed in `infra-compose` (C) |
| Sat 17:00 | Integration #1: one real document, end to end | not started |
| Sat 22:00 | Integration #2: all modules, one source each | not started |
| Sun 03:00 | Integration #3: calibration, scheduled scans | not started |
| Sun 08:00 | Feature freeze | not started |
| Sun 10:30 | Hand-in | not started |

## Modules

| Module | Owner | State | Active OpenSpec changes |
|---|---|---|---|
| scraper | A | SDLC merged; `scraper-v1` proposed (specs, design, tasks), not applied; ADRs 0101-0103 drafted, awaiting a human decision | `scraper-v1` (proposed) |
| dashboard | B | foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, mock mode, hardened container, root compose with Postgres + HTTPS gateway (`infra/`); chart library decided: Recharts ([ADR 0203](decisions/0203-dashboard-charts-recharts.md)), dependency not installed yet; web rules in `.claude/rules/web-dashboard.md`; frontend layering decided in [ADR 0204](decisions/0204-frontend-architecture.md) (existing components still to move to it, needs an OpenSpec change) | none (`web-setup` archived) |
| analytics, api, contracts | Damian | contracts v1 in `contracts/`, core frozen; ADRs 0301-0305 accepted (PR #3); mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived); analytics: `analytics-skeleton` merged (PR #10: pure pipeline, registry, M2 rules R1-R3, CLI; no worker, storage or events yet); api: `api-db-schema` applied and archived (Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack), in PR #15 with Kacper's review fixed in `api-db-schema-review-fixes`; `api/` lands on `main` with that PR; `api-v1` (REST, Socket.IO) in progress on `api/api-v1`; proposed on their own branches, awaiting approval: `infra-compose`, `analytics-worker` | `api-v1` (in progress); `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15 |

## Blockers and open decisions

- Scraper fetch client, job queue and first social platform need a human decision: option drafts are ADRs 0101, 0102 and 0103 in `.docs/decisions/` (0103 has criteria only, no research yet). Applying `scraper-v1` task groups 3 and 6 waits on 0101 and 0102.
- Open with C before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`) and who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is B's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials). `api/` from the integration plan does not exist yet; C creates it with a `CLAUDE.md` when needed.
- Contracts v1 (C): the required core is frozen and accepted by A and B ([ADR 0301](decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with A.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is C's ([ADR 0303](decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
- Social media: one platform first; which one is open.
- Root `README.md` exists (B); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
