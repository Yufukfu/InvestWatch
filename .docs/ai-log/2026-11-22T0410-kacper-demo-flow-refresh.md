---
when: Sun 04:10
who: Kacper
---

## What was done with AI

Issue #144 (from the analytics demo rehearsal on the pre-warmed `iw-demo` stack) listed four demo-flow steps and the M2 rule count that no longer matched `main`. Claude Code checked each claim before editing: the registered M2 rules in `analytics/src` (R1, R2, R3, R4, R6, R11, R12, R14-R18: 12), and the calibration values and live-alert source in `.docs/demo-analytics.md` (#141). It then aligned the dashboard demo flow with that script: no `down -v` on the cached stack, XTB forex as the live toast (up to 50 s), the M2 slider 0.10 to 0.25 with the measured numbers, saving optional and never 0.40.

## Outcome / lesson

Branch `chore/demo-flow-refresh`, docs only. Lesson: a demo script that predicts scores from an older run goes stale as soon as rules change; link the stack's own measured numbers (here `.docs/demo-analytics.md`) instead of copying them from a rehearsal comment.
