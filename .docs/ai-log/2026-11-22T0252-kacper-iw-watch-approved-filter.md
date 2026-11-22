---
when: Sun ~02:50
who: Kacper
---

## What was done with AI

A Claude Code agent fixed issue #105, two follow-ups from hen68's review of PR #102: the `approved` notice now skips drafts and PRs whose base is not the repository's default branch, and `run --limit` counts only items that start a session, so an `approved` notice never takes a slot from real work. The prompt gave it the issue, the PR review and the choice "emit outside the limit or sort last, pick with evidence".

## Outcome / lesson

Branch `chore/iw-watch-approved-filter`. Failing tests first (a draft and a stacked PR were still told; with `--limit 1` the approved notice took the only slot and the review session did not run). The agent chose to emit outside the limit rather than sort last: `--limit` bounds `claude -p` sessions and an `approved` item starts none, while sorting last would still let a backlog of work hold the notice back. A mutation of the `defaultBranch` wiring in `watch.mjs` would have survived the scan-level tests alone, so a CLI test with a `develop` default branch was added. Mutations: 8 tried, 8 caught.
