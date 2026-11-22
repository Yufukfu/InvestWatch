---
when: Sun 02:30
who: Kacper
---

## What was done with AI

A Claude Code subagent took issue #94 (`useFindings > keeps the last rows and total while the next result loads` failing in some shuffled runs). It read the hook, the test file, `web/src/test/setup.ts` and the store helper instead of running the suite in a loop, suspected a request leaking from a test that ends without awaiting it, and confirmed it with a two-test file (`selects and clears` then `keeps the last rows`): fails every time. It then reproduced the vitest shuffle in a few lines of Node to pick a seed with that order (162), so it needed under a dozen single-file runs on the 8 GB laptop.

## Outcome / lesson

Root cause: unmounting does not cancel a request RTK Query has started. `selects and clears` never awaits its first `GET /findings`; when it runs first (cold imports, slow fetch path) that request reaches MSW after the next test's `server.use`, takes call 1 of its counter, and the real first request becomes call 2 and waits forever on the gate. Fix in the shared setup, not in the one test: `makeStore` registers each store and the shared `afterEach` awaits its running queries and mutations before `server.resetHandlers()`. This also covers every other test file that uses `makeStore` or `storeWrapper`. Seed 162 failed before and passes after; seeds 253 and 11 pass. Human merges
