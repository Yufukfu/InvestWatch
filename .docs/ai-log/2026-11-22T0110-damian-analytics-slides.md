---
when: Sun ~01:10
who: Damian
---

## What was done with AI

A Claude Code side session wrote the analytics slide content for the hand-in PDF (#77, #74): ran `python analytics/eval/run.py` on `main` for the gold-set numbers, took the add-a-rule example from the real R14 commit `45bd8fee`, and summarised the PR #69 LLM swap runbook

## Outcome / lesson

Docs only (`.docs/presentation-analytics.md`). Every number is copied from the run's JSON, with its commit and gold-set hash, and the slides say the set is synthetic and the run rules-only. The rules-only run explains why LLM-backed signals (S1.5, S3.3, S3.4) show strict recall 0, which a reader would otherwise take as a broken rule
