---
when: Sat 17:30
who: Kacper
---

## What was done with AI

Ran the `trend-chart` change with Claude Code through propose, apply and review: installed Recharts per ADR 0203 and built the trend chart test-first on the contract mock, with a mutation check per group

## Outcome / lesson

Review found real gaps: day ticks used the browser timezone not UTC, the responsive path and the default mock were untested, and my first mutation script missed three caught mutants because it looked for `AssertionError` while jest-dom throws a plain `Error`. Bundle doubled (98 to 206 kB gzip), recorded with a lazy-load follow-up. The ADR's jsdom `ResizeObserver` open point is resolved: fixed size or a stub works
