---
when: Sat 18:30
who: Kacper
---

## What was done with AI

Merged `main` into PR #14 and had Claude Code work through hen68's review in the `trend-chart-review-fixes` change: checked each point against the code, fixed them test-first (chart text alternative, dash-pattern and timezone tests, day data in the mock, lazy page), with a mutation check per group

## Outcome / lesson

All four must-fix points were real; 32 mutants, all caught after one extra test (a refetch with data on screen); the `iw-reviewer` pass then found a missing error boundary around the lazy page and an untested tooltip date, both fixed. Two points were not taken as written: rebase became a merge (no force push), and module names stayed as codes because the dashboard has no names to reuse. Lesson: the mutation script must treat any failed test as red, since jest-dom matchers do not throw `AssertionError`
