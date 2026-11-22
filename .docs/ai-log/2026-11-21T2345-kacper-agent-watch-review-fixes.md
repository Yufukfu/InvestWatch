---
when: Sat ~23:45
who: Kacper
---

## What was done with AI

Had Claude Code answer Adam's request-changes reviews of PR #48 (`agent-watch-review-fixes`, ADR 0210): the headless session now publishes nothing (no `gh`, no `git push`); the runner checks the agent's commits and pushes and posts itself, and is a dry run unless `--publish`. Every command runs in the Claude Code sandbox, with no network, no writes outside the clone and no reads of credentials, shell profiles or `.env`. The session gets an env allow-list, `--setting-sources project` and `--strict-mcp-config`. Branches that change `.claude/`, `CLAUDE.md` or `.github/` are refused, as are fork PRs and a moved head. A comment carrying the agent marker is never a `/iw` answer

## Outcome / lesson

Two live `claude -p` probes (under $0.01) settled the sandbox before any code changed: it held in headless mode, but `GH_TOKEN` still reached the test runner, which the plan had not expected. That is why the env became an allow-list. Adam was right that the old session tests only compared rule strings with themselves; they were replaced by behaviour tests and a probe run with the exact runner argv
