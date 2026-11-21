# Proposal

## Why

The jury scores "skuteczność działania algorytmów scrapujących" (brief, section 6), and the first question at the demo will be what the scraper actually collected and what failed. Today the answer needs hand-written SQL: the facts are spread over `sources.last_run_status`, `documents` and `job_errors`, and none of the services shows them together. A short, honest report turns that into a one-command answer that can also be pasted into the slides.

## What Changes

- A read-only command `python -m iw_scraper.report [--since HOURS] [--json]` (a module of its own, like `iw_scraper.seed`; default window 24 h) that queries the existing tables and shows:
  - per source: name, platform, kind, active, `last_run_status`, `last_run_at`, documents (total, and new in the window), latest `fetched_at`, job errors in the window by reason;
  - overall: documents by platform and `source_kind`, the share of documents with raw HTML stored, job errors by reason, and the sources that never ran or have no documents;
  - inactive sources (for example sample sets from `scraper-sample-import`) listed in their own section, not mixed into scraper health.
- Default output is a plain table on stdout; `--json` prints one JSON object. Neither uses `print`; output goes through `sys.stdout.write`, as `seed.py` does.
- Honest by construction: the schema keeps only the last run of each source, so the report never states a success rate over many runs. It shows counts and the last status, and says so in its header.
- Out of scope: a REST route or a dashboard widget (a follow-up for Damian and Kacper, since the route would live in `api/`), any schema change or per-run history table (Damian's schema, ADR 0303), a metrics endpoint, alerts, changes to `collect.py`, `app.py` or `__main__.py`.
- Owner: Adam's module (`scraper/`).
- Contracts: none touched. It only reads `sources`, `documents` and `job_errors` through the app role, which already has `SELECT` (`infra/postgres/init/01-app-role.sh`).

## Capabilities

### New Capabilities
- `scrape-report`: a read-only summary of what the scraper collected and what failed, from the shared database.

### Modified Capabilities
<!-- none -->

## Impact

- New: `scraper/src/iw_scraper/report.py`, `scraper/tests/test_report.py`.
- Edited: `scraper/README.md` (one short section), `scraper/CLAUDE.md` module list, `.docs/status/scraper.md`, AI log row.
- No new dependency, no compose change (run it in the scraper image with `docker compose run --rm worker python -m iw_scraper.report` once `scraper-stack` is merged).
