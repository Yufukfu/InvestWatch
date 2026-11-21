# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) implemented and reviewed, in PR.
- `scraper-ingest` (database sink, `documents`, `iw:documents`) and `scraper-orchestration` (queue, schedule, scan requests, the run that joins the pieces) not started.
- ADRs 0101 and 0102 accepted on merge, 0103 criteria only.

## Active OpenSpec changes

- none (`scraper-v1` archived)

## Blockers and open decisions

- ADRs 0101 (fetch client) and 0102 (job queue) are written and take effect when the `scraper-v1` PR merges; the first social platform (0103, criteria only) is decided in `scraper-v2`.
- Open with Damian, for `scraper-ingest`: who writes the Alembic migration for the `documents` unique index, `job_errors` and a published marker (`api/` does not exist yet). `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
