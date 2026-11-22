---
when: Sat ~22:30
who: Adam
---

## What was done with AI

Claude Code proposed and applied `scraper-source-discovery` (M1: find new places to look): checked the gap against origin/main, open PRs and every worktree, then three test-first task groups with mutation checks (`mutations: 20/20`, `18/18`, `19/19`, plus 3 and 7 more for later fixes) and an `iw-reviewer` pass per group

## Outcome / lesson

ADR 0108. The reviewer found real holes the first tests missed (`localhost.`, `facebook.com.` and `0x7f.0x1` passed the host filters; a malformed DSN or source URL ended in an unlogged traceback; `--since nan` passed validation), each fixed test-first; two of its suggestions were declined with a reason in `follow-ups.md`. Lesson: a host filter needs the odd-shape cases (trailing dot, hex IP, empty label) written down before the implementation
