---
when: Sat pm
who: Damian
---

## What was done with AI

Built the `mock-server` OpenSpec change with Claude Code end to end: proposal and spec (26 WHEN/THEN scenarios), then apply per task group with failing test first, a fresh reviewer agent per group, and a retro-fitted mutation check once that rule landed on `main`

## Outcome / lesson

Reviews caught a real race (sync routes in the thread pool vs replay on the event loop: 500s under load), a half-built store on reset, tests that could not fail, and an `openapi.yaml` detail schema no response can satisfy (follow-up for the team). The mutation check (68 mutants) found 8 survivors over two runs, closed with new tests or by deleting a no-op; a stress test alone could not pin the async-routes fix, so a structural test does. Lesson: our own mock data had future timestamps, which broke "newest first" for replayed findings
