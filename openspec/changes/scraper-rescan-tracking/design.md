# Design

## Context

See proposal.md for why. State on `main` (read 2026-11-22):

- `Ingestor.ingest` dedups on `(source_id, content_hash)`: unchanged text is a silent `duplicate`, edited text is a second `documents` row for the same source, linked to nothing.
- A 404 or 410 is `Reason.HTTP_ERROR` like any other status (`fetch.py`). Only 5xx is transient (`retry.py`), so a 404 is not retried, but the run ends `failed` and counts toward the domain pause (`jobs.py`: `health.record(ok=status != "failed")`, threshold 5).
- `record_error` writes `job_errors (id, source_id, reason, detail)`; the table also has `url` (nullable) and `occurred_at`, both from Damian's `0001_initial`, and the scraper never fills `url`. `reason` is free text with only a non-empty check.
- A `web` source is one page (`sources.url`) and every version of it is one `documents` row with that `source_id`. Other platforms hold many documents per source (posts, videos), so "the latest document of the source" means nothing for them.
- The DB schema is Damian's (ADR 0303) and contracts are frozen, so no column, migration, event field or REST change here.

## Goals / Non-Goals

**Goals:**
- Make "edited" and "removed" visible for web sources, using only what the schema already has.
- Say exactly how the api derives both states, so Damian can implement issue 71 without a call.
- Never turn a flaky 404 into a permanent "removed" label, and never count a removal against the scraper's health.

**Non-Goals:**
- Exact state for revert and reappear (needs a column, decision 5).
- Non-web platforms, soft 404s, redirect-to-home removals.
- Any api, web or analytics code.

## Decisions

### 1. "Changed" is derived from `documents`, the scraper only reports it

For a web source, the documents ordered by `created_at` (server clock; `fetched_at` is the scraper's clock) form the version history, and the newest one supersedes the older ones. The scraper adds nothing to the tables. On insert it looks up the previous document id (one query before the insert, informational), returns it in the ingest result and logs `rescan_outcome: changed`. Rejected: a `supersedes` key in `documents.payload` (invisible to SQL filters without a JSON path, tempting a contract field that is frozen) and a new column (Damian's migration, not needed for the demo case).

### 2. "Removed" is a `gone` row in `job_errors`

The api derives, per web source: `removed` = the latest `job_errors` row with `reason = 'gone'` is newer (`occurred_at`) than the latest document's `created_at`; `changed` (for a finding on document D) = D is not the newest document of its source. `job_errors` is already the scraper's observation log; `reason` is free text, so `gone` needs no migration. Rejected: an event field on `scan.finished` (contract), a new table (schema is Damian's), and reusing `http_error` plus a status in `detail` (the effectiveness report and the api would have to parse text).

### 3. Confirm with one repeat request, record once

A 404 or 410 on a web source with a stored document is repeated once in the same run (a second `wait_turn`, the same identity and session). Only two matching answers make it `gone`. This keeps one flaky 404 from labelling an ad removed until the next change. It is recorded once: the check "a `gone` row exists that is newer than the latest document" decides, so a still-missing page adds no row per re-scan, and a page that was replaced and removed again records a new one. Removal is only for a source that already stored something; a never-collected 404 stays `http_error`. `fetch()` stays one attempt (the existing requirement); the repeat is the collector's, like the redirect loop.

### 4. Unchanged, reverted and reappeared are logged, not stored

A duplicate leaves no trace in the tables by design (ADR 0104). The collector asks the store for the source's newest document hash and whether a `gone` row is newer than it, and logs one `rescan_outcome` line: `unchanged` (hash is the newest), `reverted` (an older hash), `reappeared` (a `gone` is newer than the newest document). These lines are the demo evidence and the reason the effectiveness report can say what re-scans found; they are not derivable from the tables.

### 5. The exact version needs two columns, proposed not assumed

Without a column, two cases are wrong in the tables: a page that reverts to an earlier text (the newest row stays B, so the api says "changed" although the page shows A), and a page that returns unchanged after a removal (the `gone` row stays newer, so the api says "removed"). Both need either `documents.last_seen_at` bumped on every duplicate or a `removed_at`/`cleared_at` pair. The proposal to Damian goes on issue 71 with this exact wording; if he accepts, the scraper bumps it in the duplicate branch (one `UPDATE`), and no spec here changes except a new requirement. Until then both are documented limitations (ADR, README), and the demo scripts avoid them (edit, remove).

### 6. A removal is a success for the queue

`AttemptResult` keeps `error = None` for `gone`: the collector records the row itself (through the ingestor's recorder, which already redacts and never raises) and returns no error. `derive_status(0, 0)` is `ok`, `health.record(ok=True)` resets the failure count, nothing is retried. Rejected: returning the error and special-casing `gone` in `jobs.py` in three places (retry, status, health), which spreads one rule over the queue.

### 7. Where the code goes

`types.py` (`Reason.GONE`, `JobError.url`), `ingest/errors.py` (write `url`), `ingest/store.py` (`previous_document`, `removal_state`: newest document id, hash, `created_at`, and the newest `gone` `occurred_at` in one query), `ingest/pipeline.py` (`changed` outcome, `record_gone`), `collect.py` (the web flow's fetch branch). The open change `scraper-social-x-youtube` adds `known_urls` to `pgstore.py`; the two lookups answer different questions and share nothing, so no reuse is forced. Both edit `collect.py` in different branches of the flow; whichever merges second rebases.

## Risks / Trade-offs

- Wrong state on revert or reappear → documented (ADR, README, issue 71), logged as `rescan_outcome`, closed by the decision 5 columns if Damian agrees.
- A site that answers 404 for a moment and 200 on the repeat is fine, but one that answers 404 twice for a minute still records `gone` → the next stored document clears it; acceptable for a monitoring tool, and the log shows the sequence.
- A site that removes content with a 200 "not found" page is not detected → out of scope, said in the README.
- `gone` rows appear in the effectiveness report as an error reason → intended: they are counted under their own reason, never mixed with `http_error`.
- Two lookups per re-scan (previous document, removal state) → one indexed query each on `(source_id)`; informational, their failure is logged and never fails the ingest or the run.
- Clock difference between `created_at` and `occurred_at` → both are server `now()` defaults of the same database, so the comparison is consistent.
