---
when: Sun 04:15
who: Kacper
---

## What was done with AI

Issue #127: the iw-watch conflict tests failed on the Linux CI runner. Adam's fix in #125 gave the tests a fixed identity, but the runner itself still committed merges with whatever identity the machine had. Claude Code checked that `git var GIT_AUTHOR_IDENT` / `GIT_COMMITTER_IDENT` fail exactly when a commit would (with `user.useConfigOnly` and no global config), then added a preflight in `iw-watch run` that asks git outside any repository, as a fresh clone sees it, and exits 2 with setup guidance before any GitHub call or agent session. Tests first; mutations 5 tried, 5 caught after one more test.

## Outcome / lesson

Branch `chore/iw-watch-git-identity`. Lesson: the mutation pass first reported 5 survivors because `--test-name-pattern` is case-sensitive and skipped one of the two new tests; a mutation run that reports every mutant surviving is checked for a broken harness before the tests are blamed. The one real survivor (checking inside the main checkout, where a local-only `user.email` would hide the problem) got its own test.
