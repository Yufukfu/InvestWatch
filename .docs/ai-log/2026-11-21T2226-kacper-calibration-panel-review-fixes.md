---
when: Sat 2026-11-21
who: Kacper
---

## What was done with AI

Claude Code fixed the request-changes review of PR #45 in `calibration-panel-review-fixes`: checked each item against the code, wrote the tests first, and checked the focus test red against the old remount key. The save guard was checked against three mutants (hard-coded module, refetch guard removed, module-switch guard removed); each was caught

## Outcome / lesson

The reviewer's 98-mutant run was not repeated, and the App mount test, the page double-submit test and the marker placement in a browser were not mutated or run. These are in the change's `follow-ups.md`. The spec's decimal examples were left as they are
