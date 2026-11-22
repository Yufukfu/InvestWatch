# Proposal

## Why

The scraper side of issue #71 (Adam, PR #108) records a removed web page as one `job_errors` row with `reason = 'gone'`, `detail` `HTTP 404`/`HTTP 410` and `url` = the source URL as entered. The API derivation from `api-rescan-state` (PR #87) counts only `reason = 'http_error'` and matches `job_errors.url` against the document's final URL, so:

1. a removed page never shows as `removed` (wrong reason), and
2. a source whose URL redirects never shows as `removed` either (the entered URL differs from the stored final URL).

Both were blocking findings in the review of PR #108. Fixing them on the API side keeps the scraper as it is.

## What Changes

- `api/src/investwatch_api/rescan.py`: a gone job error is `reason IN ('gone', 'http_error')`; old `http_error` rows keep working.
- A web document with a `source_id` matches gone job errors by `source_id` alone: a web source is one page (the scraper fetches `source.url` only), and its `job_errors.url` is the entered URL. Other platforms hold many pages per source and keep the URL match, so a 404 on one post does not remove a channel's other posts.

No contract change: job error reasons are internal values, not in `contracts/`. No table or migration change.

Module: `api/` (Damian). Consumer: `web/` reads `scrape_meta.rescan` unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities

- `rest-api`: the re-scan `removed` state counts the scraper's `gone` rows and matches web pages by source.
