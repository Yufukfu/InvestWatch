# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) is merged (PR #19).
- `scraper-ingest` (database sink, `documents`, `iw:documents`, republish sweep) is implemented against Damian's `0001_initial`, in review (PR #22) and archived in that PR.
- `scraper-orchestration` (queue, schedule, scan requests, the run that joins the pieces) not started.
- ADRs 0101 and 0102 are accepted (PR #19); ADR 0104 (ingest order, republish sweep) takes effect when PR #22 merges; 0103 criteria only.

## Active OpenSpec changes

- none (`scraper-v1` archived; `scraper-ingest` archived in PR #22; `scraper-author-provenance` for issue 36 is archived in its own PR)

## Blockers and open decisions

- The first social platform (ADR 0103, criteria only) is decided in `scraper-v2`.
- Wiring is unassigned: nothing calls `Ingestor`, `sweep` or `Storage.check_bucket` yet, and the v1 `JobErrorSink` is synchronous while `record_error` is async; to be settled in `scraper-orchestration` (follow-up 1 of `scraper-ingest`).
- Two redactors exist: `reporting.redact` (userinfo only, used by `fetch.py` and `reporting.py`) and `ingest.errors.redact` (full). Keep the full one and drop the other when `scraper-orchestration` wires the pieces (follow-up 3 of `scraper-ingest`).
- Issue 36 (author provenance): no collector on `main` sets `author`; the ingest drops it from a page. A `scrape_meta` "author verified" flag would need a contract change and is not proposed in the contract yet.
- `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
