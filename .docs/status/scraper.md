# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) is merged (PR #19).
- `scraper-ingest` (database sink, `documents`, `iw:documents`, republish sweep) is implemented against Damian's `0001_initial`, in review (PR #22) and archived in that PR.
- `scraper-orchestration` (queue, run lock, concurrency cap, events, scan requests, scheduler, health, `run_source`, the `worker` and `scheduler` commands) is implemented and tested end to end on real Redis, PostgreSQL and MinIO; the opt-in live KNF smoke run passed once (2026-11-21). The PR is next.
- `content-hash-definition` (issue #31): the `content_hash` definition (NFC) is written into integration-plan §3 and ADR 0105, pinned by scraper tests; no scraper code changed. Analytics (Damian) still has to read the stored hash instead of recomputing it with NFKC (proposal in the issue).
- ADRs 0101 and 0102 are accepted (PR #19); ADR 0104 (ingest order, republish sweep) takes effect when PR #22 merges; 0103 criteria only.

- `scraper-v2-sources` (12 vetted M1/M2/M3 web sources in `scraper/seeds/sources.toml`, validated and idempotent seed loader, host-guard test, opt-in live check) is implemented and tested, stacked on `scraper-orchestration` (PR #38). The opt-in live check passed for all 12 pages on 2026-11-21 (HTTP 200, no redirect, robots allowed, text present). M3 positives come from `scraper-v2-social` (Telegram channels) and the icobench list page; naming a business from the KNF warnings list is an optional, human-only follow-up.

## Active OpenSpec changes

- `scraper-orchestration` (PR #38 merged; its review fixes are in PR #49); `scraper-author-provenance` for issue 36 is archived in its own PR (#41)
- `scraper-v2-sources` (PR #43)

## Blockers and open decisions

- The first social platform (ADR 0103, criteria only) is decided in `scraper-v2`.
- Wiring (`Ingestor`, `sweep`, `Storage.check_bucket`, the job-error sink) is done in `scraper-orchestration` (`app.py`).
- Two redactors exist: `reporting.redact` (userinfo only, used by `fetch.py` and `reporting.py`) and `ingest.errors.redact` (full). Keep the full one and drop the other when `scraper-orchestration` wires the pieces (follow-up 3 of `scraper-ingest`).
- Issue 36 (author provenance): no collector on `main` sets `author`; the ingest drops it from a page. A `scrape_meta` "author verified" flag would need a contract change and is only proposed (`scrape_meta.author_source`, in the issue 36 reply), not in the contract; its PR must keep the flag off a page-supplied `scrape_meta`.
- `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
