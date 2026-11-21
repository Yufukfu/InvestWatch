# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) is merged (PR #19).
- `scraper-ingest` (database sink, `documents`, `iw:documents`, republish sweep) is implemented against Damian's `0001_initial`, in review (PR #22) and archived in that PR.
- `scraper-orchestration` (queue, run lock, concurrency cap, events, scan requests, scheduler, health, `run_source`, the `worker` and `scheduler` commands) is implemented and tested end to end on real Redis, PostgreSQL and MinIO; the opt-in live KNF smoke run passed once (2026-11-21). The PR is next.
- `scraper-stack` deploys the scraper in the one-command stack (`scraper/compose.yaml`: `worker`, `scheduler`, `seed`; root include line; `scraper/tests/stack.sh`; ADR 0106; `seed` rejects an invalid cron). Implemented and checked locally (12 config + 10 run scenarios, 13 mutations caught); PR next.
- ADRs 0101 and 0102 are accepted (PR #19); ADR 0104 (ingest order, republish sweep) takes effect when PR #22 merges; 0103 criteria only.

## Active OpenSpec changes

- `scraper-stack` (PR next)

## Blockers and open decisions

- Kacper must OK the one-line `scraper/compose.yaml` entry in the root `compose.yaml` `include:`.
- `scraper-v3-render` task 3.2 plans to create the same `scraper/compose.yaml` with `stop_grace_period: 45s`: amend it to add only `renderer`, the `render` network and the worker's renderer settings, keeping 60 s (ADR 0106).
- The first social platform (ADR 0103, criteria only) is decided in `scraper-v2`.
- Wiring (`Ingestor`, `sweep`, `Storage.check_bucket`, the job-error sink) is done in `scraper-orchestration` (`app.py`).
- Two redactors exist: `reporting.redact` (userinfo only, used by `fetch.py` and `reporting.py`) and `ingest.errors.redact` (full). Keep the full one and drop the other when `scraper-orchestration` wires the pieces (follow-up 3 of `scraper-ingest`).
- `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
