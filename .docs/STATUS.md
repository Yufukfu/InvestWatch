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
| scraper | Adam | SDLC merged; `scraper-ingest` implemented against Damian's `0001_initial` (document build, validation, dedup insert, MinIO, `iw:documents` after commit, republish sweep, `job_errors` sink; in review); `scraper-v1` and `scraper-orchestration` in progress; ADRs 0101, 0102 and 0104 accepted with this change, 0103 criteria only | `scraper-ingest` (in review), `scraper-v1`, `scraper-orchestration` |
| dashboard | Kacper | foundation: app shell, RTK Query client generated from `contracts/openapi.yaml`, mock mode, hardened container, root compose with Postgres + HTTPS gateway (`infra/`); Recharts installed ([ADR 0203](decisions/0203-dashboard-charts-recharts.md)) with the trend chart (`web/src/features/trend/`, hour/day switch on `GET /stats/trend`, data table as text alternative, lazy-loaded: main bundle about 101 kB gzip plus a 107 kB trend chunk; jsdom needs a fixed chart size or a `ResizeObserver` stub, verified); web rules in `.claude/rules/web-dashboard.md`; frontend layering ([ADR 0204](decisions/0204-frontend-architecture.md)) applied to health, summary, findings and trend, with a lint check on components | none (`web-setup`, `trend-chart`, `trend-chart-review-fixes` archived) |
| analytics, api, contracts | Damian | contracts v1 in `contracts/`, core frozen; ADRs 0301-0305 accepted (PR #3); mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived); analytics: `analytics-skeleton` merged (PR #10: pure pipeline, registry, M2 rules R1-R3, CLI; no worker, storage or events yet; both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`); api: `api-db-schema` applied and archived (Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack), in PR #15 with Kacper's review fixed in `api-db-schema-review-fixes`; `api/` lands on `main` with that PR; `api-v1` (REST, Socket.IO) in progress on `api/api-v1`; proposed on their own branches, awaiting approval: `infra-compose`, `analytics-worker` (needs `main` merged in now that PR #10 is in) | `api-v1` (in progress); `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15 |

## Blockers and open decisions

- Scraper fetch client and job queue are decided in ADRs 0101 and 0102 (agent-written, effective when the `scraper-ingest` PR merges). The first social platform is open: ADR 0103 has criteria only, no research yet.
- Open with Damian before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`) (the Alembic migration is settled: Damian's `0001_initial` in `api/migrations/` has the `documents` unique index, `job_errors` and `stream_published_at`; `redis`, `minio` and `minio-init` come with Damian's `infra-compose`).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is Kacper's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials).
- Contracts v1 (Damian): the required core is frozen and accepted by Adam and Kacper ([ADR 0301](decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is Damian's ([ADR 0303](decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
- Social media: one platform first; which one is open.
- Root `README.md` exists (Kacper); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
