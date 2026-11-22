---
when: Sat ~16:10
who: Damian
---

## What was done with AI

Applied `analytics-skeleton` with Claude Code: proposal first, then per task group a failing test, the implementation, a scripted mutation check and a fresh `iw-reviewer` subagent; meanwhile three parallel sessions drafted the `infra-compose`, `api-db-schema`/`api-v1` and `analytics-worker` proposals

## Outcome / lesson

Per-group reviews found real bugs the tests missed: `FirmRef.authorized` defaulting to true, unvalidated URLs, prices like `500 zł.` not ending a sentence, a legal-forms-only firm name fuzzy-matching every text, and R3 passing on risk denials ("bez żadnego ryzyka", "Ryzyko? Minimalne."). Mutation checks exposed dead code and equivalent mutants. The CLI test caught a reserved `module` log key that unit tests at WARNING level hid. The parallel proposals both used ADR number 0306: lesson, reserve ADR numbers before parallel sessions start
