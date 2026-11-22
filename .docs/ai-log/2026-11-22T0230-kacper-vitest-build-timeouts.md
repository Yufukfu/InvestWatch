---
when: Sun ~02:30
who: Kacper
---

## What was done with AI

A Claude Code side session took issue #60 (web image build failing on Vitest timeouts under load): read the six timed-out tests and the one real failure, reproduced the `FindingsPage > changes the status` failure in a single-file run by adding 600 ms to the PATCH and the refetch, then raised the Testing Library and Vitest defaults and moved the suite out of the default image build

## Outcome / lesson

The `Potwierdzone` failure was a test-timing bug, not a product bug: one 1 s `waitFor` had to cover two round trips (PATCH, then the detail refetch its invalidation triggers). The six 5 s timeouts were mostly each file's first test, which pays for the first render under CPU contention. No benchmarks or full-suite runs on the 8 GB laptop; the full suite is left to CI. Human merges
