---
when: Sun ~06:30
who: Adam
---

## What was done with AI

A sub-agent refreshed the hand-in docs from a read-only gap report: counts recomputed from the filesystem and `gh` at `origin/main` `313c625b`, M2 rule counts read from the `implemented:` flags, the LLM default taken from ADR 0318, two new slides (how we build with AI, advertiser to firm graph) plus a what-is-unique list, a minimal root README with the configuration table moved to `infra/README.md`, and honest brief-compliance rows. Prompt approach: verify every report claim against code before acting.

## Outcome / lesson

Branch `chore/hand-in-refresh`, docs only. The report's counts and its M2 "13 of 19" were stale in places (R9 and R10 merged in #160, scraper and X/YouTube PRs merged), so each was recomputed. The M2 gold figures after #160 come from `analytics/README.md`; the agent could not re-run the evaluation here (Python 3.9 only), so they are unverified by a rerun. The human decides the PR merge and whether `doc/` stays.
