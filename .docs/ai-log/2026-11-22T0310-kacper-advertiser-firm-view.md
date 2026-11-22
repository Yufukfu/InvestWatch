---
when: Sun 03:10
who: Kacper
---

## What was done with AI

Issue #72 (who promotes which licensed firm, M1) handed to a Claude Code sub-agent with a shared brief: lowest-effort version from the issue (a table, not a graph), built client-side from `GET /findings`, no contract change, tests first. The agent wrote the OpenSpec change `advertiser-firm-view`, then a pure grouping function, a data hook that pages `module=M1&page_size=200` up to a fixed 3-page cap with a fixed number of RTK Query hook calls (rules of hooks), and a presentational table, each behind failing tests and a scripted mutate-and-restore check.

## Outcome / lesson

Change `advertiser-firm-view` (PR for issue #72). The static contract mock has no repeat advertiser among its M1 findings, so the repeat highlight is pinned by component and grouping tests, not visible on the static mock. Running several agents' Vitest suites on one 8 GB machine at once made mutation runs slow; the coordinator limited every agent to scoped test files with one worker. The human decides on merge.
