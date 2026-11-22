---
when: Sat ~17:45
who: Damian
---

## What was done with AI

Had Claude Code replace the A/B/C person labels with Adam, Kacper and Damian across the repo (PR #16): a scripted regex rewrite with exceptions for the article "A", "S.A." in mocks, git flags and code, then a word-level diff review of every changed line

## Outcome / lesson

First pass ran on a `main` 83 commits behind `origin/main`; caught at push time and redone on the fresh tree. The script misread the article "A" twice ("A later decision", "A Redis Stream"), caught in diff review. It also rewrote 12 archived OpenSpec changes (kept on purpose, noted in the PR) and the `contracts/openapi.yaml` description, dropped after Kacper's review because the committed `web/` snapshot would go stale
