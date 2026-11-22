---
when: Sun 05:25
who: Damian
---

## What was done with AI

A Claude Code side session of the coordinator wrote and implemented the OpenSpec change `analytics-m2-visual-rules`: the visual M2 rules R5, R7, R8 and R13 read from the renderer's per-viewport `blocks`, worded after the ZASÓB criteria. Each rule was one test-first commit with a scripted mutation check and an `iw-reviewer` pass, and the rules-only gold evaluation was run before and after.

## Outcome / lesson

All four rules score P/R 1.0 on their gold examples, and M2 recall at 0.1 rose from 0.739 to 0.783. Three mutation runs each had one survivor, all from a test fixture that made a check redundant: a risk block holding only the warning sentence, and a past-performance sentence that always carries a `%` figure. R13's own gold example also exposed a gap in the shared past-performance detector: a year range like `2021-2025` was not read as the past. Fixing that once in the shared detector also cleared R14's applicability error. Lesson: run a new rule against its gold example before writing its unit tests, because the gold example finds detector gaps that hand-made fixtures do not.
