# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) is merged (PR #19).
- `scraper-ingest` (database sink, `documents`, `iw:documents`, republish sweep) is implemented against Damian's `0001_initial`, in review (PR #22) and archived in that PR.
- `scraper-orchestration` (queue, run lock, concurrency cap, events, scan requests, scheduler, health, `run_source`, the `worker` and `scheduler` commands) is implemented and tested end to end on real Redis, PostgreSQL and MinIO; the opt-in live KNF smoke run passed once (2026-11-21). The PR is next.
- `scraper-stack` deploys the scraper in the one-command stack (`scraper/compose.yaml`: `worker`, `scheduler`, `seed`; root include line; `scraper/tests/stack.sh`; ADR 0106; `seed` rejects an invalid cron). Implemented and checked locally (12 config + 10 run scenarios, 13 mutations caught); PR next.
- `content-hash-definition` (issue #31): the `content_hash` definition (NFC) is written into integration-plan §3 and ADR 0105, pinned by scraper tests; no scraper code changed. Analytics (Damian) still has to read the stored hash instead of recomputing it with NFKC (proposal in the issue).
- `scraper-effectiveness-report` is implemented and reviewed (`python -m iw_scraper.report`, a read-only summary of collected documents and job errors from the shared tables; no success rate, because only the last run per source is stored). The PR is next; a REST route or dashboard widget for it is a follow-up for Damian and Kacper.
- `scraper-sample-import` (`python -m iw_scraper.sample_import`: saved HTML or text, for the samples handed out at the stand and offline demo replay, through the same `Ingestor`) is implemented and tested; rehearsed in the image on two saved pages, not through the full stack (analytics findings and the dashboard alert not exercised). PR #56.
- ADRs 0101 and 0102 are accepted (PR #19); ADR 0104 (ingest order, republish sweep) takes effect when PR #22 merges; 0103 criteria only.

- `scraper-v2-sources` (12 vetted M1/M2/M3 web sources in `scraper/seeds/sources.toml`, validated and idempotent seed loader, host-guard test, opt-in live check) is implemented and tested, stacked on `scraper-orchestration` (PR #38). The opt-in live check passed for all 12 pages on 2026-11-21 (HTTP 200, no redirect, robots allowed, text present). M3 positives come from `scraper-v2-social` (Telegram channels) and the icobench list page; naming a business from the KNF warnings list is an optional, human-only follow-up.

## Active OpenSpec changes

- `scraper-stack` (PR #52); `scraper-orchestration`, `scraper-author-provenance`, `scraper-v2-sources` and `content-hash-definition` are merged (PRs #38, #49, #41, #43, #44)
- `scraper-effectiveness-report` (PR #57)
- `scraper-sample-import` (PR #56)

## Blockers and open decisions

- Kacper must OK the one-line `scraper/compose.yaml` entry in the root `compose.yaml` `include:`.
- `scraper-v3-render` task 3.2 plans to create the same `scraper/compose.yaml` with `stop_grace_period: 45s`: amend it to add only `renderer`, the `render` network and the worker's renderer settings, keeping 60 s (ADR 0106).
- The first social platform (ADR 0103, criteria only) is decided in `scraper-v2`.
- Wiring (`Ingestor`, `sweep`, `Storage.check_bucket`, the job-error sink) is done in `scraper-orchestration` (`app.py`).
- Two redactors exist: `reporting.redact` (userinfo only, used by `fetch.py` and `reporting.py`) and `ingest.errors.redact` (full). Keep the full one and drop the other when `scraper-orchestration` wires the pieces (follow-up 3 of `scraper-ingest`).
- Issue 36 (author provenance): no collector on `main` sets `author`; the ingest drops it from a page. A `scrape_meta` "author verified" flag would need a contract change and is only proposed (`scrape_meta.author_source`, in the issue 36 reply), not in the contract; its PR must keep the flag off a page-supplied `scrape_meta`.
- `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- The real UKNF sample format is unknown until the stand: `sample_import` reads HTML, `.txt` and `.md`; a PDF or DOCX reader is one function in `READERS`, added on the day.
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
