---
when: Sun ~01:15
who: Damian
---

## What was done with AI

A Claude Code side session implemented Damian's part of issue #71: the re-scan state of a finding's document (`current`/`changed`/`removed`) derived on read in `GET /findings/{id}`, after checking the frozen contracts for a slot and the scraper for what a re-scan and a 404 actually write

## Outcome / lesson

Branch `api/rescan-finding-state`. The issue's default ("derive from existing fields, no contract change") held only for the detail: `Finding` is closed, so the state goes in the open `scrape_meta`, and a list badge needs a contract field (`rescan_state`, follow-up). The scraper writes no `job_errors.url` today, so `removed` from a job error waits for Adam's part.
