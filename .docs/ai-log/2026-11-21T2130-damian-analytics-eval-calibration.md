---
when: Sat ~21:30
who: Damian
---

## What was done with AI

A Claude Code side session proposed and applied `analytics-eval-calibration` (stage 3) on the `analytics-worker` base while a coordinating session relayed Damian's answers: the gold set (67 synthetic lines with fictional firms, every ZASÓB rule paired, M1/M3 from the Opis scope and annex 3), an evaluation with the API's counting, an idempotent `calibration_points` writer, a default-stack one-shot service and the API summing analyst labels with the gold run (ADR 0312). Per task group: failing test first, mutation check with a backup-and-restore script, a read-only reviewer subagent every two or three groups.

## Outcome / lesson

Branch `analytics/analytics-eval-calibration`, not pushed. The reviewers found what tests missed: `splitlines()` cut gold lines on U+2028 inside text, duplicate JSON keys silently dropped labels, an unescaped `@` in the DB password reached the log through the libpq host error, one shared run id re-stored unchanged modules. Labels were written before running the rules; the disagreements went to `follow-ups.md` as rule issues, never as label changes. Checking the gold set on the stage-2 M1/M3 branch showed rules-only M3 never reaches its 0.7 default. Lessons: `iw-reviewer` was not registered in a session opened outside the repo (a general-purpose agent following its file stood in); shell heredocs turned `\n` in Python edits into real newlines, so multi-line edits went through a script file. Later the same day the branch moved onto `analytics-m1-m3` (#35), gained `zasob-example` lines, specs split for OpenSpec 2.1.1's 500-character rule, and Damian's decision that the default thresholds come from the evaluation (ADR 0316: best F1 per module, M1 0.65, M2 0.25, M3 raised to its 0.4 gate cap), pinned by a test across `api` and `analytics`.
