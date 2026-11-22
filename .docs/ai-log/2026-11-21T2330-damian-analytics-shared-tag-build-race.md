---
when: Sat ~23:30
who: Damian
---

## What was done with AI

A Claude Code side session (started from the review of Adam's PR #52) fixed the shared-tag build race in `analytics/compose.yaml`: `build:` only on `analytics`, `analytics-eval` reuses the image (the `api-migrate`/`api` pattern), plus a regression test that failed on main's file first.

## Outcome / lesson

Branch `analytics/compose-single-build`. The check command from the brief (`-f infra/compose.yaml -f api/compose.yaml -f analytics/compose.yaml build`) failed 4/4 before reaching the race: Compose resolves every relative path from the first `-f` file's directory, so `build: .` meant `infra/`; the header's "without the root file" command had never worked. Fixed with `build: ../analytics`. On fresh tags the fix built 4/4; a control copy with `build:` on both services failed 1/4 with "already exists". Lesson: a race that shows up one run in four needs a control run, not only green runs of the fix.
