---
when: Sat ~21:00
who: Kacper
---

## What was done with AI

Had Claude Code change the process so agents push their own branch and open the PR while humans approve and merge (ADR 0207): found every place that states the old rule (CLAUDE.md, SDLC, CODE_REVIEW, `iw-pr-review`, OpenSpec config, hook comment, `settings.json` permissions), edited them together and checked the hook tests still pass

## Outcome / lesson

The first draft claimed the rule stayed "enforced by code", but it loosened a permission (`git push` and `gh pr create` from `ask` to `allow`) without the PR body saying so, and Adam's review of the PR proved the claim wrong. The first draft also cited the review criteria file by bare name and `docs-check` caught it
