---
when: Sun ~01:45
who: Adam
---

## What was done with AI

Had Claude Code implement `scraper-rescan-tracking` (issue 71, scraper half) from a saved session file: five task groups test-first, each with a scripted mutation check (6, 15, 11 and 5 mutants, all caught) and an `iw-reviewer` subagent per logic group; the design had already been fixed after a cold read against the code.

## Outcome / lesson

Branch `scraper/scraper-rescan-tracking`, PR #108. The mutation script first reported six "survivors" that were a harness bug (host paths inside the container) and later 15 invalid runs (zsh does not split an unquoted variable); the script now labels anything but a real test failure as an invalid run. A test of a non-web source passed with its guard removed because both ingests failed validation; asserting the outcomes made it red. Reviewers found nothing blocking. Merging `main` showed the old log table had been replaced by per-entry files, so the row moved here.
