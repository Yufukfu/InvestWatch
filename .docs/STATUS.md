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
| scraper | A | `scraper-v1` (fetch, parse, politeness, guards) implemented and reviewed, in PR; `scraper-ingest` (database sink, `documents`, `iw:documents`) and `scraper-orchestration` (queue, schedule, scan requests, the run that joins the pieces) not started; ADRs 0101 and 0102 accepted on merge, 0103 criteria only | `scraper-v1` (applied) |
| dashboard | B | n/a | none yet |
| analytics, api, contracts | Damian | plans written; contracts v1 in `contracts/`; ADRs 0301-0305 in PR #3, see `.docs/decisions/README.md` | none yet |

## Blockers and open decisions

- ADRs 0101 (fetch client) and 0102 (job queue) are written and take effect when the `scraper-v1` PR merges; the first social platform (0103, criteria only) is decided in `scraper-v2`.
- Open with C: the `scrape_meta.scraper` value (`scraper-v1` task 1.3, needs Damian's review of the enum PR before Sat 17:00; `contracts/` freezes Sat 14:30) for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`), and, for `scraper-ingest`, who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is B's (`scraper/`, `analytics/`, `web/`, `contracts/`, `.docs/`, `doc/` for UKNF materials). `api/` from the integration plan does not exist yet; C creates it with a `CLAUDE.md` when needed.
- Contracts v1 exist as a draft in `contracts/` (C) and are still to be confirmed by A and B; rendering metadata (`blocks`, screenshots) still to be discussed with A.
- Social media: one platform first; which one is open.
- Root `README.md` exists (B); its Quick Start is pending the deployment ADR. Per-service READMEs are stubs.
- `.docs/security-audit.md` is promised by `integration-plan.md` §7 and not created yet; created at the first `pip-audit` / `npm audit` run.
