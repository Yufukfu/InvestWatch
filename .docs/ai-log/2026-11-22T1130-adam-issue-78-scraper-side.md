---
when: Sun ~11:30
who: Adam
---

## What was done with AI

A Claude Code session did the scraper side of issue #78: read Damian's recorded run against the code on `main` (seed files, scan-request consumer, scheduler, retry and job-error paths, merge time of PR #67) instead of restarting the shared stack, and wrote only what the run shows, with "not checked" for the rest

## Outcome / lesson

Branch `scraper/demo-rehearsal-evidence`, docs only (`.docs/STATUS.md` scraper evidence, `.docs/status/scraper.md`). The per-source document split, scraper logs and scheduled scans are not in the issue, so they stay open. Found `.docs/status/scraper.md` still calling the renderer PR pending after it merged.
