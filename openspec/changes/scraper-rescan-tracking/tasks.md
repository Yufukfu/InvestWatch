# Tasks

## 1. Reason `gone` and the URL on job errors

- [ ] 1.1 Test first (`scraper/tests/test_types.py`, `test_errors.py`): add `gone` to `EXPECTED_REASONS` (the set-equality test), `oops` is still rejected; a URL with userinfo or a token query is stored redacted and cut to a maximum length; `JobError(url=...)` is written to `job_errors.url` and `redact` still applies to the detail; every existing error without a URL still stores NULL
- [ ] 1.2 Add `Reason.GONE` and `JobError.url`; `record_error` writes the column through `redact` and a length cap (test PostgreSQL, `scraper/tests/schema.sql` already has `url`)
- [ ] 1.3 Mutation check — mutations: N tried, N caught

## 2. Changed, unchanged, reverted, reappeared

- [ ] 2.1 Test first (`scraper/tests/test_ingest_store.py`, test PostgreSQL): `removal_state` of a source with no document, one document, two documents, and a `gone` row older and newer than the newest document; `previous_document` returns the newest other row created before the new one, ties by id; equal timestamps do not read as "newer"
- [ ] 2.2 Test first (`scraper/tests/test_ingest_rescan.py`): the spec scenarios of "Report a changed page" and "Report an unchanged or reverted re-scan" (first collection, edited page with `outcome` still `inserted` and `previous_document_id` set, earlier rows keep every column value, a duplicate found after losing the insert race, lookup failure after the insert, unchanged, reverted, reappeared, a non-web document logs nothing), reading the `rescan_outcome` log line
- [ ] 2.3 `ingest/store.py` lookups; `ingest/pipeline.py` `previous_document_id`, `Ingestor.rescan_state`, the `rescan_outcome` log line; failures of the lookups are logged and never fail the ingest
- [ ] 2.4 Mutation check — mutations: N tried, N caught

## 3. Removed page in the web flow

- [ ] 3.1 Test first (`scraper/tests/test_collect_gone.py`, stub server): the six scenarios of "Record a removed page once, with its URL" (410 twice after a stored document, a redirect to a 404, 404 on the next re-scan makes one request and stores no second row, replaced then removed again stores a new row, never stored stays `http_error`, 503 and 403 are never `gone`, lookup failure falls back to `http_error`) plus "one flaky 404", "confirmation answers something else" (503 and 429 keep their status and `Retry-After`) and "URL is redacted"; the test's ingestor fake gains `rescan_state` and `record_gone`
- [ ] 3.2 `Ingestor.record_gone` and the 404/410 branch of the web flow in `collect.py` (one confirmation request with its own `wait_turn`, same identity and session, skipped when a `gone` is already newer than the newest document; stored URL is `source.url`). Rebase on `scraper-social-x-youtube` first if it has merged
- [ ] 3.3 Mutation check — mutations: N tried, N caught

## 4. A removal is not a failed run

- [ ] 4.1 Test first (`scraper/tests/test_jobs_gone.py`, real Redis): a `gone` job ends `ok` with `documents = 0`, is not requeued, clears its attempt counter and `sources.last_run_status = ok`; five `gone` jobs do not pause the domain while five 503s still do (the pause requirement is in `web-collection`)
- [ ] 4.2 Collector returns a result with no error for `gone`; no change to `jobs.py` unless 4.1 shows one is needed
- [ ] 4.3 Mutation check — mutations: N tried, N caught

## 5. End to end and the derivation for Damian

- [ ] 5.1 End to end on the test stack (real Redis, PostgreSQL, MinIO, stub web server): scan a page, edit it, scan again, remove it, scan again; assert the two rows, the `gone` row with its URL, and `scan.finished` `ok` each time
- [ ] 5.2 Pin the api derivation as a test: the two SQL queries of design decisions 1 and 2, run on the state of 5.1, return `changed` for the first document and `removed` for the source; also pin the two known-wrong cases (revert to an earlier text still derives "changed", unchanged return after a removal still derives "removed") with a comment naming design decision 5; these queries are what goes to Damian
- [ ] 5.3 Mutation check — mutations: n/a, wiring group; behaviour verified by the end-to-end run

## 6. Closing

- [ ] 6.1 Apply iw-docs-update: an ADR with the derivation rule and its two limits (next free number across all branches, 0109 is taken), `scraper/README.md` (how to read `rescan_outcome`, what `gone` means, soft 404s not detected), `.docs/status/scraper.md`, and add the iw-ai-log row; `docs-check` prints `docs-check: ok`
- [ ] 6.2 Post the derivation queries and the decision 5 migration proposal as a comment on issue 71 (owners Damian and Kacper); link it from the PR body
- [ ] 6.3 Run iw-pr-review and fix real findings
