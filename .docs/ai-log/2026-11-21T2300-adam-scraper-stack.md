---
when: Sat ~23:00
who: Adam
---

## What was done with AI

Had Claude Code deploy the scraper in the compose stack (`scraper-stack`): moved the work to a fresh worktree on `origin/main` when the hook blocked a branch reset, wrote `stack.sh` red first, then the compose file, and found that `seed` stored an invalid cron the scheduler would skip on every tick (fixed test-first); the reviewer showed three checks of `stack.sh` could not go red, all fixed and re-mutated (13 of 13 caught)

## Outcome / lesson

A stack check needs a mutation run of its own: a green script that cannot fail proves nothing; one mutation (`replicas`) was caught for the wrong reason (duplicate key) until redone
