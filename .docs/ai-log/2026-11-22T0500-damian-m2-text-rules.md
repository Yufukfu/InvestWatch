---
when: Sun 05:00
who: Damian
---

## What was done with AI

A Claude Code side session of the analytics coordinator built the two missing M2 text rules as the OpenSpec change `analytics-m2-text-rules`:
- R10 language consistency, which was cut from `analytics-llm-p0`, rules-only with a per-sentence language guess;
- R9 comprehensibility, LLM-first: a rules signal gives `uncertain`, and the LLM's 1-5 rating decides.

Each group went test first, with a mutation check and a reviewer pass. The classes live in a new module so a parallel visual-rules session could work on `rules/m2.py` without conflicts.

## Outcome / lesson

Two mutation checks caught weak tests:
- a tie test whose tie sat below the minimum signal, so the tie rule never ran;
- an R9 evidence choice that every test passed by accident.

Adding R9 moved the rules-only best M2 threshold from 0.1 to 0.05. Damian decided that a rules-only `uncertain` without evidence is not scored, which is a catalogue flag rather than a special case in R9, so the threshold stays at 0.1. The lesson: even a low-severity `uncertain` shifts the M2 score curve, so check the threshold test before saying a rule is "only additive".
