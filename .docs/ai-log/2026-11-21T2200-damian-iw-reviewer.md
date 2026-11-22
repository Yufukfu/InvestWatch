---
when: Sat ~22:00
who: Damian
---

## What was done with AI

Asked Claude Code to cut review time and noise; it rewrote `iw-reviewer`, `.claude/CODE_REVIEW.md`, `iw-commit-cycle` and `iw-pr-review`

## Outcome / lesson

Found that each per-group review re-read the whole branch (`merge-base..HEAD`), security ran as a second full pass, and the reviewer had to list PLAUSIBLE items and "declined to judge" notes that each became a `follow-ups.md` row; 9 of 26 archived changes were review-fix rounds. Now: each range reviewed once, security in the same call, a blocking-only bar with a concrete trigger, re-review of fix commits only, 2 rounds max. Human decides the merge
