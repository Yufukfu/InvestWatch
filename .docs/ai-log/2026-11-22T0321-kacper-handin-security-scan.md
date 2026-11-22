---
when: Sun ~03:20
who: Kacper
---

## What was done with AI

After PR #100 merged, Claude Code started `security.yml` by hand on `main` with `offline: true` as the hand-in scan. It read the job logs rather than the green status, then linked the run in `.docs/security-audit.md`.

## Outcome / lesson

Run 44975537124 on `3de46bde`: all green, no open finding.

Reading the logs showed a limit the green status hid. The offline OSV-Scanner job sees only the direct Python pins: 16 packages in `api/requirements-dev.txt`, against 90 online. Without the network it cannot resolve the transitive dependencies of a `requirements.txt`. An earlier reviewer note said resolution was Maven-only, which was wrong for pip. The limit is now written in the runbook, and the follow-up is a full Python lockfile for an air-gapped scan.

Lesson: compare a scan's package counts across modes, not only its pass or fail.
