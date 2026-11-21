# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` proposed (specs, design, tasks), not applied.
- ADRs 0101-0103 drafted, awaiting a human decision.

## Active OpenSpec changes

- `scraper-v1` (proposed)

## Blockers and open decisions

- Fetch client, job queue and first social platform need a human decision: option drafts are ADRs [0101](../decisions/0101-scraper-fetch-client.md), [0102](../decisions/0102-scraper-job-queue.md) and [0103](../decisions/0103-first-social-platform.md) (0103 has criteria only, no research yet). Applying `scraper-v1` task groups 3 and 6 waits on 0101 and 0102.
- Open with Damian before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
