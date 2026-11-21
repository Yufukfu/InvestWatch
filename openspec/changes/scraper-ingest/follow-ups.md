# Follow-ups

Every row has a disposition. "Deferred" names where it is picked up; nothing here blocks this change.

| # | Finding | Disposition |
|---|---|---|
| 1 | Nothing calls `Ingestor`, `sweep` or `Storage.check_bucket` yet, and the wiring has no owner on paper: the sink adapter (`scraper-v1` defines a synchronous `JobErrorSink.record`, this change ships `async record_error(pool, error)`), the `page` dict with `html` and `text` (v1's `ParsedPage` has neither `html` nor `http_status`), `check_bucket` at startup and the scheduled sweep. | Deferred: to be settled between `scraper-v1` and `scraper-orchestration` before either is merged. Needs the module A owner's decision. |
| 2 | Rebase conflicts with `scraper-v1` and `scraper-orchestration`: `scraper/requirements.txt` (`redis` 5.2.1 here, 8.1.0 on `scraper-v1`, `arq` on orchestration may cap `redis`), `scraper/requirements-dev.txt`, and `scraper/tests/conftest.py` (both add one). | Deferred: resolved by whoever merges second. Keep a `redis` that works with `arq`, take `pytest` 9.0.3 and `pytest-asyncio` 1.5.0 (PYSEC-2026-1845), keep both sets of fixtures, run the whole suite and `pip-audit`. |
| 3 | `iw_scraper.reporting.redact` on `scraper-v1` is a weaker duplicate of `ingest.errors.redact`. | Deferred: keep one implementation (this one) after the rebase. |
| 4 | The manual Python CI job cannot run this suite (no dev dependencies, no PostgreSQL, Redis or MinIO). | Fixed in a separate PR, branch `chore/ci-python-services`; this PR does not claim CI covers these tests until it merges. |
| 5 | `job_errors.url` is never written: `JobError` (shared types) has no `url`. | Deferred: add the field in a follow-up change if the dashboard needs the URL. |
| 6 | An orphan object can remain after a hard crash between upload and insert, or when a task is cancelled during `put_html` (the worker thread keeps uploading). The reverse race, cancelled just after the commit, removes the object of a committed row. | Deferred: a periodic list-and-diff of `iw-raw` against `documents.html_object_key`. Every error path and an ordinary cancellation already clean up. |
| 7 | The sweep holds its transaction and row locks while it publishes: worst case batch size times `PUBLISH_TIMEOUT_S` (100 x 5 s) with a failing Redis, although the first failure ends the loop. | Deferred: lower the batch or the timeout if a degraded Redis shows up in testing. |
| 8 | Redaction limits: an unquoted secret value containing spaces keeps its tail (`password=a b c`), and masking over-redacts some benign text (an `@` in a path or query). | Accepted: callers must still never put credentials in a `detail`; leaking is worse than over-masking. |
| 9 | A NUL character in `text` fails the insert and is recorded as `storage_error` after the upload (misclassified, but cleaned up). | Deferred: strip or reject NUL in the parser (`scraper-v1`). |
| 10 | `Redis MAXLEN` trimming for `iw:documents`. | Deferred: not decided here (ADR 0104). |
| 11 | ADR number 0104 may collide with another scraper stream's ADR. | Check at merge; renumber in the second PR if it does. |
