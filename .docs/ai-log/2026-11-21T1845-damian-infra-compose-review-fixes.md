---
when: Sat ~18:45
who: Damian
---

## What was done with AI

Claude Code fixed Kacper's two reviews of PR #18 in `infra-compose-review-fixes`: merged `main` twice without rebasing (the branch was pushed), proved `api-migrate` exits 0 on a project-scoped network, wrote the licence section and the ADR 0202/0306 updates, made `init-env.sh` idempotent, and strengthened two smoke checks that could pass without proving anything

## Outcome / lesson

Kacper's review caught what three agent reviews missed: a stale STATUS row, an accepted ADR contradicting the code, a promised README licence note that was never written, macOS-only breakage in the smoke test, and two vacuous checks. The agent's own new `openssl` test first passed vacuously on Git Bash (a `C:/...` PATH entry splits at the colon); its mutation check exposed that. Lesson: run every new test against a mutant, and let a human review docs against promises made in ADRs
