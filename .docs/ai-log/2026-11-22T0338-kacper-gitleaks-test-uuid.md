---
when: Sun 03:38
who: Kacper
---

## What was done with AI

The Gitleaks job failed on every open PR at once. Claude Code read the job log: one `generic-api-key` hit, a UUID v5 firm key (`key: '<uuid>'`) in a web test fixture on PR #129's branch. The checkout uses `fetch-depth: 0`, so every PR scans every branch, and a pushed commit cannot be rewritten (no force push). It added a rule-level allowlist entry for that exact line shape in web test files and checked it with the pinned Gitleaks image: the old config reports the hit, the new config scans 872 commits on all remote branches with no leaks, and a scratch web test file with two key-shaped random values (one written exactly like the UUID line) still reports both.

## Outcome / lesson

Branch `chore/gitleaks-test-uuid`. A false positive on any pushed branch fails every PR until the allowlist is on `main`, so such a fix merges first. Lesson: when testing an allowlist with `gitleaks dir`, scan `.` from the repo root; an absolute path breaks `^web/...` path patterns and makes the entry look broken.
