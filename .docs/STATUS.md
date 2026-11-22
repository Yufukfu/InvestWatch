# Status

Team-wide state only: milestones and decisions that need the whole team. Module state, active OpenSpec changes and module blockers live in one file per domain (below); edit only your own file, never another owner's ([ADR 0205](decisions/0205-status-per-domain.md)). Agents read this file and then the file of their domain at session start. The owner of a milestone edits its row here.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | contracts: required core frozen, optional fields provisional until Sat 17:00 ([ADR 0301](decisions/0301-contracts-v1.md), accepted); compose infra: Postgres + HTTPS gateway up (Kacper, PR #6); Redis, object storage (MinIO, bucket `iw-raw`) and the optional Ollama profile `llm` in PR #18 (`infra-compose`, Damian) |
| Sat 17:00 | Integration #1: one real document, end to end | analytics + api verified on a clean stack from `main` c810a14 (#78, 2026-11-22): scan request → scraper → `iw:documents` → analytics → `findings` + `iw:events` → `GET /api/findings` through the gateway. Dashboard part (Kacper) and scraper part (Adam) pending in #78 |
| Sat 22:00 | Integration #2: all modules, one source each | analytics: M1, M2 and M3 all fire on real seeded sources (#78): 223 documents from 17 sources, 72 findings (M1 54, M2 5, M3 13), 10 `finding.high_risk` events, 0 analytics errors. Gaps: hosted LLM unavailable (1 of 5 calls OK, then breaker, 71 of 72 findings rules-only); one negative control (Grant Thornton) is high-risk M3 0.78 because S3.4 stays `uncertain` without the LLM |
| Sun 03:00 | Integration #3: calibration, scheduled scans | analytics: `analytics-eval` stores the gold-set run on `up`, `GET /api/calibration` returns the curve per module through the gateway (#78). Moving the threshold in the dashboard and scheduled scans not checked by analytics |
| Sun 08:00 | Feature freeze | not started |
| Sun 10:30 | Hand-in | not started |

## Domain status

| File | Owner | Covers |
|---|---|---|
| [status/scraper.md](status/scraper.md) | Adam | `scraper/` |
| [status/dashboard.md](status/dashboard.md) | Kacper | `web/`, `infra/` |
| [status/platform.md](status/platform.md) | Damian | `analytics/`, `api/`, `contracts/` |

A blocker goes in the file of the domain it blocks. Naming another owner in your file is fine; changing their file needs their OK.

## Team-wide blockers and open decisions

- Repository layout is Kacper's (`scraper/`, `analytics/`, `web/`, `contracts/`, `api/`, `infra/`, `.docs/`, `doc/` for UKNF materials); confirm with him before adding directories.
- Demo path: until the api (`api-v1`, PR #21) or a mock service is in the root compose, `docker compose up` shows the dashboard's error states only; the dashboard is developed against `contracts/mock-server` run as a separate container ([ADR 0206](decisions/0206-dashboard-data-from-backend.md), decision in PR #25). Accepted for now; before the demo and the Sunday 10:30 hand-in `docker compose up` must run the whole system. Owner Kacper, with Damian for the backend.
- Dependency and secret scans: results go in each PR body ("Security scans" section), not in a shared file; `.docs/security-audit.md` keeps service notes and the hand-in run ([ADR 0209](decisions/0209-supply-chain-scanning.md), [integration-plan.md](integration-plan.md) §7). Target: the scans as required CI checks on every PR.
