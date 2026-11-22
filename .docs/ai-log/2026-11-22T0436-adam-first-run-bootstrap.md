---
when: Sun 04:36
who: Adam
---

## What was done with AI

A Claude Code session read the challenge brief and the repository, found that a clean `docker compose up` leaves the database empty (sources are only scanned on cron or by hand), and proposed the OpenSpec change `first-run-bootstrap`: a one-shot that queues a scan per scheduled never-run source, a `status` readiness command, and a brief-to-evidence table. A cold read of the finished artifacts against the code caught that bootstrap would have scanned the X and YouTube rows that ADR 0109 keeps manual. Implementation followed `iw-commit-cycle`: test first, mutation checks, one `iw-reviewer` pass per group.

## Outcome / lesson

The live `stack.sh` group and a clean-stack run found two things the unit tests could not: `up --wait` fails on a finished one-shot unless something depends on it with `required: false`, and the documented `docker compose run --rm bootstrap ...` rebuilt images and put the build log in front of the JSON (the command needs `--no-deps -T`). A reviewer's note about never-expiring Redis keys was rejected: seed ids are random per database. On a clean stack the pipeline filled itself in about three minutes (numbers in the scraper status file).
