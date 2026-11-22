---
when: Sat ~21:00
who: Damian
---

## What was done with AI

Had Claude Code turn the red CI job `Specs and hooks` (PR #24) green: reproduced it with the CI-pinned OpenSpec 2.1.1 rather than the local 1.2.0, read the length rule in the 2.1.1 source, and moved the overflow of 14 requirements into their own scenarios in the change `openspec-strict-format`. Headers and scenario names were kept so the in-flight `analytics-llm-p0` and `analytics-m1-m3` deltas still line up, and a word diff checked that no clause was lost

## Outcome / lesson

The local 1.2.0 CLI reported all specs valid, so the failure showed only in CI: validate with the version CI pins (`CLAUDE.md` setup). The first fix was a hand edit of `openspec/specs/`, against the "archive writes specs" rule; it was redone as a change whose archive reproduces the same files (apart from blank lines the archive normalises)
