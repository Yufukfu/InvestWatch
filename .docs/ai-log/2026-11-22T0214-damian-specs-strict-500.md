---
when: Sun ~02:30
who: Damian
---

## What was done with AI

The coordinator reported that the CI job `Specs and hooks` was red on `main`, and a Claude Code side session fixed it with `specs-strict-500`. Three requirements merged in #86, #87 and #104 were longer than OpenSpec 2.1.1's limit of 500 characters before the first scenario. The session moved the extra sentences word for word into `**AND**` lines of the scenarios that test them, plus one new scenario, the way #37 did. Behaviour did not change.

## Outcome / lesson

The local `openspec` CLI was version 1.2.0 and passed 32/32, while CI's pinned 2.1.1 failed. The session found the gap by checking the version first, then validated with `npx -y @fission-ai/openspec@2.1.1`. Every validation in this repo should run that pinned command, not a global install. The edit to `shared-infrastructure` is format-only and goes to Kacper for review.
