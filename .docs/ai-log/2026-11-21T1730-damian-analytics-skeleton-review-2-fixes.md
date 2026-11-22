---
when: Sat ~17:30
who: Damian
---

## What was done with AI

Kacper's Claude re-review of PR #10 raised 2 important findings and 5 nits on the new head; Claude Code probed each one (all 7 real) and fixed them test-first in the `analytics-skeleton-review-2-fixes` change (28 mutants, all caught after one extra test), then a fresh `iw-reviewer` pass found one high-severity regression in those fixes

## Outcome / lesson

Both important findings were crash paths our tests never exercised: unchecked YAML params that failed on the first document, and one exception losing the whole CLI batch. The mutation check exposed a test that could not fail (a long hyphenated name matched either way), so a short-name case was added. One suggestion (narrowing the `stra` stem) was declined: it changes no outcome. The reviewer then showed that requiring genitive `ryzyka` let `zero ryzyk` and `nie ma ryzyka straty` pass as warnings: a regex fix for one false fail had caused false passes, caught only by probing realistic denials against the old and new catalogue
