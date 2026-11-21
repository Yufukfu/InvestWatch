# Proposal

## Why

Integration #2 (Sat 22:00) needs at least one real source per module (M1, M2, M3) and the demo needs real pages, but `sources` is empty except for the one KNF row that `scraper-orchestration` seeds. A web-sources research pass fetched candidate pages with our own engine (robots allowed, HTTP 200, main text in static HTML) and produced a vetted list; this change turns it into a reviewed, repeatable seed so every teammate and the demo stack start with the same sources.

## What Changes

- A tracked seed file `scraper/seeds/sources.toml` with the vetted web sources for M1, M2 and M3 (name, URL, `source_kind`, `target_modules`, `schedule_cron`, optional `render`).
- An idempotent seed command that inserts the entries into `sources`, keyed by URL, and never overwrites a row (the dashboard owns later edits). It extends the `seed.py` that `scraper-orchestration` task 3.5 adds for the KNF row instead of adding a second script.
- Validation of the file before any write: platform `web` only, closed `source_kind` and module sets, https URLs, valid 5-field cron, unique URLs.
- An opt-in live check (marker `scraper_live`) that fetches each seeded URL once and fails on a redirect to another URL, a non-200 status or an empty text, so a stale seed is found before the demo.
- An optional per-entry `render` flag, read by `scraper-v3-render`, for the two pages that need `blocks` and screenshots (XTB IKE, mBank IKE). It is not stored in `sources`.
- M3 gets two negative controls now and its real positives later: a human picks 1-2 entries from the KNF public warnings list, which stays an open question.

Out of scope: the KNF registry parsers (`registry_firms`, `registry_warnings`; Damian's), Playwright and `blocks`/screenshots (`scraper-v3-render`), social sources (`scraper-v2-social`), dashboard source editing, any change to the `sources` table or `source` contract.

Touches no contract, REST route or event. It writes existing `sources` columns only. Owner: scraper (Adam).

## Capabilities

### New Capabilities
- `source-seeds`: the vetted set of web sources and the idempotent, validated way they get into `sources`.

### Modified Capabilities
<!-- none: web-collection and document-ingest are unchanged; a host with no parser uses the generic parser already -->

## Impact

- `scraper/seeds/sources.toml` (new), `scraper/src/iw_scraper/seed.py` (from `scraper-orchestration`, extended), `scraper/tests/` (seed tests, live check).
- Depends on `scraper-orchestration` being merged (`run_source`, the PostgreSQL `SourceStore`, `seed.py`); implementation starts after that merge.
- Docs: `scraper/CLAUDE.md`, `scraper/README.md` (seed step), `.docs/status/scraper.md`, AI log row.
