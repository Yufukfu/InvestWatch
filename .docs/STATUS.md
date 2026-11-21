# Status

Team-wide state only: milestones and decisions that need the whole team. Module state, active OpenSpec changes and module blockers live in one file per domain (below); edit only your own file, never another owner's ([ADR 0205](decisions/0205-status-per-domain.md)). Agents read this file and then the file of their domain at session start. The owner of a milestone edits its row here.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | contracts: required core frozen, optional fields provisional until Sat 17:00 ([ADR 0301](decisions/0301-contracts-v1.md), accepted); compose infra: Postgres + HTTPS gateway up (Kacper, PR #6), Redis and object storage proposed in `infra-compose` (Damian) |
| Sat 17:00 | Integration #1: one real document, end to end | not started |
| Sat 22:00 | Integration #2: all modules, one source each | not started |
| Sun 03:00 | Integration #3: calibration, scheduled scans | not started |
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
- `.docs/security-audit.md` collects every `pip-audit` / `npm audit` run ([integration-plan.md](integration-plan.md) §7); add a row per audit before merge.
