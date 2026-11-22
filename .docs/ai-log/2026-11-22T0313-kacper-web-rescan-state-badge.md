---
when: Sun 03:13
who: Kacper
---

## What was done with AI

An agent built the web part of issue #71 (change `web-rescan-state-badge`) from Damian's checklist and the merged api (PR #87): a defensive `parseRescan` for the open `scrape_meta` object and a separate `RescanNotice` component, kept apart so it merges cleanly with the parallel export-button work in the same panel. Tests came first, then a scripted mutate-and-restore check per group.

## Outcome / lesson

Mutation checks found a surviving guard (`typeof id`: an array `[uuid]` passes the UUID regex through string coercion), which got a test. The group review flagged that `Date.parse` accepts loose strings such as `"Nov 22"`; it was fixed with an ISO-8601 check. Reading PR #108 against the api showed that the scraper records a removal as `reason = 'gone'` while the api counts only `http_error`, so `removed` would not have appeared; PR #113 had just fixed this in the api on `main`, so the branch was rebased instead of patched from `web/`. Full Vitest runs timed out on lazy-chunk tests under load average 31 from parallel agents; scoped runs with one worker were used.
