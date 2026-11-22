# 0110. How a re-scan shows "changed" and "removed" without a schema change

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written; accepted by the human via the `scraper/scraper-rescan-tracking` PR

## Context

The brief's Module 1 asks for periodic updates that show what happened to an ad since it was flagged. Before this change a re-scan that found edited text inserted a second `documents` row linked to nothing, and a page that disappeared was the generic `http_error` of any server hiccup. The schema is Damian's (ADR 0303) and the contracts are frozen, so neither a column nor an event field was available. Issue 71 asks for the scraper half. Spec: [`openspec/changes/archive/2026-11-22-scraper-rescan-tracking/`](../../openspec/changes/archive/2026-11-22-scraper-rescan-tracking/design.md).

Facts read from the code on `main` (2026-11-22): `Ingestor.ingest` dedups on `(source_id, content_hash)`, so edited text is a new row and unchanged text leaves no trace; `job_errors` already has nullable `url` and `occurred_at` that the scraper never filled, and `reason` is free text; `fetch()` hides redirect hops, so a 404 behind a redirect is indistinguishable from one on the source URL.

## Options considered

1. **Derive from existing columns** (chosen). `changed` = the document is not the newest row of its source (`created_at DESC, id DESC`); `removed` = the newest `job_errors` row with reason `gone` is newer than the newest document. The scraper only records: a `gone` job error with the source URL, and `previous_document_id` plus a `rescan_outcome` log line on a re-scan. Evidence: the end-to-end test `test_a_page_is_edited_reverted_removed_and_comes_back_and_the_api_derivation_follows` runs the two queries on the real tables.
2. **A `supersedes` key in `documents.payload`.** Rejected: invisible to SQL filters without a JSON path, and it invites a contract field after the freeze.
3. **A new column or table** (`last_seen_at`, `removed_at`). Exact in every case, but it is Damian's migration; proposed on issue 71, not assumed.
4. **Reuse `http_error` with the status in `detail`.** Rejected: the effectiveness report and the api would parse text.

A removal is confirmed by one more request in the same run before it is recorded, so one flaky 404 does not label an ad removed until the next change. The confirmation is skipped when a `gone` is already newer than the newest document, so a page that stays missing costs one request per re-scan and adds no row. A `gone` run returns no error, so the queue ends it `ok`, does not retry it and does not count it toward the domain failure pause (the site answered normally).

## Decision

Option 1 for web sources. `Reason.GONE` joins the closed set; `JobError.url` is written to `job_errors.url` (userinfo dropped, cut to 300 characters, redacted). Every web re-scan logs one `rescan_outcome` line: `changed`, `unchanged`, `reverted`, `reappeared` or `gone`. Non-web platforms are not classified: they hold many documents per source, so "the newest document of the source" means nothing for them.

## Consequences

- The api (Damian) and the dashboard (Kacper) can label a web ad changed or removed with two queries and no migration; the queries are pinned in `scraper/tests/test_e2e.py` and posted on issue 71.
- **Two derivations are wrong and pinned as known limits** (the end-to-end test asserts the wrong value with a comment): a page that reverts to an earlier text still derives "changed" (the newest row is the edited one), and a page that returns unchanged after a removal still derives "removed" (the `gone` row stays newer). Both need `documents.last_seen_at` bumped on a duplicate, or a `removed_at`/`cleared_at` pair; if Damian accepts, the scraper does one `UPDATE` in the duplicate branch and the two tests change on purpose. `rescan_outcome` logs `reverted` and `reappeared`, so the demo has evidence either way.
- Soft 404s (a 200 page saying "not found") and redirects to a home page are not detected.
- Absence of a post from a channel listing, and per-post removal on X and YouTube, are not covered: no direct per-URL fetch exists for them.
- `gone` shows up in the effectiveness report under its own reason, never mixed with `http_error`.
