# Proposal

## Why

Module 1 of the brief asks for "mechanizm okresowej aktualizacji": re-scans must show what happened to an ad since it was flagged. Today a re-scan that finds edited text silently inserts a second `documents` row that nothing links to the first, and a page that disappeared is the same generic `http_error` as a server hiccup, so neither "edited" nor "removed" can be shown. This is the scraper half of issue 71; the api (Damian) and the dashboard (Kacper) read what this change records.

## What Changes

- **Changed page:** when a re-scan of a `web` source inserts a row and the source already had an earlier one, the ingest result carries `previous_document_id` (the outcome stays an insert) and a structured log line says `rescan_outcome: changed`. The earlier rows stay as they are; the state is derivable from `documents` alone (design decision 1).
- **Removed page:** an HTTP 404 or 410 on a `web` source that has at least one stored document, confirmed by one more request in the same run, is recorded once as a job error with the new reason `gone` and the source URL (redacted) in `job_errors.url`, instead of `http_error`. The confirmation is not a retry. A source that never stored a document keeps `http_error`.
- **A removal is not a failed run:** a `gone` run is not retried, does not count against the domain's failure pause, and ends `ok` with `documents = 0`. The job error row is the observation, not a failure of the scraper.
- **Re-scan outcome log:** every web re-scan logs one JSON line, `rescan_outcome`, with `unchanged`, `changed`, `reverted`, `gone` or `reappeared`, so the demo and the effectiveness report have evidence even for the cases the tables cannot show (design decision 4).
- `JobError` gets an optional `url`, written to the existing `job_errors.url` column.
- The closed reason set gains `gone`; the 404 sentence of `web-collection` is narrowed accordingly.
- **Documented hand-off, no code for Damian here:** how the api derives `changed` and `removed` from existing columns (design decision 2), and what needs a migration if he wants it exact (design decision 5, to be raised on issue 71).

Out of scope, each a follow-up or another owner: the superseded-finding state in the api and the badges in `web/` (Damian, Kacper, issue 71); absence of a post from a Telegram or other channel listing, and per-post removal on X and YouTube (no direct per-URL fetch exists for them yet); soft 404s (a 200 page saying "not found") and redirects to a home page; a `last_seen_at` or `removed_at` column (needs Damian's migration, ADR 0303). Owner: scraper (Adam).

## Capabilities

### New Capabilities

### Modified Capabilities
- `document-ingest`: a re-scan that inserts a row for a source that already had one reports it as changed; an unchanged or reverted page is reported, never silently identical.
- `web-collection`: a 404 or 410 on a source with stored documents is `gone`, recorded once with its URL; the closed reason set gains `gone`.
- `web-collection` also: a `gone` outcome is a success for the domain failure pause.
- `scan-orchestration`: a `gone` run is not requeued and ends `ok`; the retry requirement says the confirmation request is not a retry.

## Impact

- Code: `scraper/src/iw_scraper/types.py` (`Reason.GONE`, `JobError.url`), `ingest/errors.py` (write `url`), `ingest/store.py` (previous-document lookup, removal state), `ingest/pipeline.py` (`changed` result, a recorder for `gone`), `collect.py` (404/410 branch of the web flow), `ingest/errors.py` also redacts and caps `url`. `jobs.py` needs no change: a `gone` run has no `AttemptResult.error`.
- Contract: touches none. No `documents` column, no migration, no REST route and no event field; `scan.finished` keeps its shape. `job_errors.reason` is free text in Damian's schema; `url` is an existing nullable column.
- Docs: `.docs/status/scraper.md`, the scraper README (re-scan outcomes and how to read them), an ADR for the derivation rule and its limits, a reply on issue 71 with the derivation for Damian and the migration proposal.
- Overlap: the open change `scraper-social-x-youtube` adds a `known_urls` lookup on the Postgres store. This change needs a different query (latest document and last `gone` of a source) and puts it in `ingest/store.py`; it also restructures the web flow in `collect.py`, so it merges first and this change rebases on it (design, decision 7).
