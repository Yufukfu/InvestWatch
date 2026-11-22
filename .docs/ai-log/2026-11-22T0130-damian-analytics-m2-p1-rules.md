---
when: Sun ~01:30
who: Damian
---

## What was done with AI

A Claude Code side session implemented `analytics-m2-p1-rules` (R11, R12a, R12b, R15, R16, rules-first) from its approved plan: 8 task groups, each test-first with a scripted mutation check (one line per group in `tasks.md`), and a fresh reviewer agent per group. The group reviews caught real defects in the agent's own regexes: a catalogue lint crash on class ranges like `[+-9]`, a fee exclude that was quadratic on a digit run (the timing test had no word-plus-digits input), `podatny` read as a tax word, and an LLM question that asked for date arithmetic without a reference date (now decided in code from `fetched_at`). The gold set (ADR 0312) caught what unit tests did not: R11 alone moved the measured M2 default 0.1 -> 0.2 until the shared past-performance detector learned `2021: 2,1%` year tables and the source markers learned a comparison method. Lesson: per-group review plus the gold run is worth it, but review rounds on one regex must be capped (coordinator decision after two rounds). Also: Python `write_text` on Windows writes CRLF; write bytes.

## Outcome / lesson

M2 F1 0.737 -> 0.829 at the unchanged default 0.1
