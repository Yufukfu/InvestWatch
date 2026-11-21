# Status

Last updated: 2026-11-21 (Sat) by A. Update this file when a milestone moves or a blocker appears; agents read it at session start.

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
| scraper | A | SDLC setup PR in progress; first change `scraper-v1` next | none yet |
| dashboard | B | n/a | none yet |
| analytics, api, contracts | C | plans written | none yet |

## Blockers and open decisions

- Scraper fetch library (noble-tls vs alternatives) needs an ADR after reading the real API.
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Repository layout is defined by B (team decision). `scraper/` and the service list in `.claude/hooks/git-guard.js` (`SERVICE_DIRS`) are assumptions to confirm with B.
- Contracts v1 still to be confirmed by A and B; rendering metadata (`blocks`, screenshots) still to be discussed with A.
- Social media: one platform first; which one is open.
