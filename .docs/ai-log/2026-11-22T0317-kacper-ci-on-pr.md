---
when: Sun ~03:00
who: Kacper
---

## What was done with AI

Kacper asked whether anything runs automatically as a PR gate. Claude Code checked with `gh` and gave him the facts:
- `ci.yml` was manual only. Its last run on `main` was 2026-11-21 19:49 UTC, and 55 PRs had been merged since without it.
- The branch is not protected, and rulesets answer 403 on the current plan.
- Job times and the Actions-minutes cost per push, with billing rounding each job up to a whole minute.

Kacper chose advisory checks watched in review over paying or going public. Claude Code added the `pull_request` trigger and `concurrency` to `ci.yml`, wrote ADR 0213, and updated `.claude/SDLC.md`, the runbook and `.docs/STATUS.md`.

## Outcome / lesson

Branch `chore/ci-on-pr`. The first answer about "the PR gate" only covered `security.yml` and missed that tests, lint and types never ran on PRs. The user's follow-up questions found the gap. Lesson: when someone asks what runs automatically, list every workflow's triggers, not only the one just built.
