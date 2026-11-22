---
when: Sun 06:17
who: Damian
---

## What was done with AI

A Claude Code session started by the coordinator updated the analytics numbers in the hand-in docs (`.docs/hand-in.md`, `.docs/presentation-analytics.md`, `.docs/demo-analytics.md`) after PRs #159 and #160 brought M2 to 18 of 18 rules and its default threshold to 0.05 (ADR 0319). It re-measured them on `main` `61238394` instead of copying them: one rules-only run and two DeepSeek Flash runs of `analytics/eval/run.py`. Docs only; no code, spec or threshold change.

## Outcome / lesson

The rules-only run matched the README table exactly. The first DeepSeek run did not: M2 at 0.05 gave 0.917 / 0.957 / 0.936 (2 false positives), while a second run matched the README (1.0 / 0.957 / 0.978). The LLM is not deterministic. The docs now give both M2 runs instead of the best one. Lesson: measure an LLM run at least twice before you publish one number from it.
