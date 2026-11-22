---
when: Sun 02:45
who: Damian
---

## What was done with AI

A Claude Code session, started from the review of PR #108, fixed the two api-side mismatches the review found: the api counted only `http_error` job errors while the scraper writes `gone`, and matched `job_errors.url` against the final URL while the scraper stores the entered one. Tests first (both failed on `main`), then the fix, then a 7-mutant check

## Outcome / lesson

Branch `api/rescan-gone-source-match`. The first draft matched every page by `source_id`; reading the scraper showed that social sources hold many posts per source, so only web documents with a `source_id` match by source. A mutant that dropped the null-`source_id` guard survived until a test was added for it (SQLAlchemy turns `== None` into `IS NULL`). The fix is on the api side, so the scraper stays unchanged
