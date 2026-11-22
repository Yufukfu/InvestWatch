---
when: Sun 03:10
who: Kacper
---

## What was done with AI

Issue #72 (who promotes which licensed firm, M1) handed to a Claude Code sub-agent with a shared brief: lowest-effort version from the issue (a table, not a graph), built client-side from `GET /findings`, no contract change, tests first. The agent wrote the OpenSpec change `advertiser-firm-view`, then a pure grouping function, a data hook that pages `module=M1&page_size=200` up to a fixed 3-page cap with a fixed number of RTK Query hook calls (rules of hooks), and a presentational table, each behind failing tests and a scripted mutate-and-restore check.

Before merge, the web owner chose to put hen68's two mockups (graph and relation page, issue #72) into the same PR. A second sub-agent merged `main` (#137 hash-routed pages), added the `Powiązania` page with the graph drawn as inline SVG (no new dependency), filters, the side table and the relation drill-down, and changed the repeat rule to the mockup's (2+ firms or 5+ findings), again test-first with scripted mutation checks. It compared its screenshots with the mockups in headless Chrome at 1440 px and 390 px, using a throwaway local API that served the mockup's sample advertisers, and iterated on spacing and layout until they matched.

## Outcome / lesson

Change `advertiser-firm-view` (PR for issue #72). The static contract mock has no repeat advertiser among its M1 findings, so the repeat highlight is pinned by component and grouping tests, not visible on the static mock. Running several agents' Vitest suites on one 8 GB machine at once made mutation runs slow; the coordinator limited every agent to scoped test files with one worker. Headless Chrome enforces a minimum window width, so phone screenshots need device emulation (DevTools protocol), not `--window-size`. The human decides on merge.
