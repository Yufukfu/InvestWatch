---
when: Sun 04:47
who: Damian
---

## What was done with AI

A Claude Code side session refreshed the analytics numbers in the hand-in docs (`.docs/presentation-analytics.md`, `.docs/hand-in.md`). It re-ran the rules-only gold-set evaluation on `main` at `dd30d668`, matched it against the DeepSeek Flash run recorded at `0434553b` (no analytics code change in between), and replaced the stale numbers: 12 of 18 M2 rules (P0 and P1), M1/M2/M3 precision and recall rules-only and with DeepSeek Flash at the hand-in defaults (M1 0.75, M2 0.1, M3 0.4), the M2 per-rule table and slider, and the LLM slide (hosted DeepSeek Flash, local Gemma, cache, rules-only fallback).

## Outcome / lesson

The slides still said 8 of 18 rules and M2 P 0.93 / R 0.61 after four analytics PRs had merged. Every number now comes from one of the two named runs, and the M1 at 0.75 numbers were read from the run's threshold points, not estimated. Lesson: put the measured sha next to every number so a stale slide is visible at a glance.
