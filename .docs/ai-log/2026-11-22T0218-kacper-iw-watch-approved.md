---
when: Sun ~02:00
who: Kacper
---

## What was done with AI

A Claude Code session added an `approved` notice to `iw-watch`: scan reads `reviewDecision`, the runner notifies without starting a session, and the Discord notifier pings the user with "your PR is approved! You can merge it now".

## Outcome / lesson

Branch `chore/iw-watch-approved` (PR #102). A first run test failed because the fixture's approval had a body, which the scan also (correctly) treats as review feedback; the test now uses an empty approval. hen68's review found that a running check did not hold the notice back and that the past-the-cap test never ran the cap branch; both fixed test-first in 0dba602, the rest is issue #105. Not sent through a real webhook yet.
