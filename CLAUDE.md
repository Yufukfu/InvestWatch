# InvestWatch

Hackathon system (HackNation, UKNF challenge) that finds risky investment content online. Lightweight separate services, one `docker compose up`, open-source and on-premise only (no paid APIs at runtime). Hand-in: Sun 2026-11-22, 10:30.

## Docs first

Business logic, contracts and decisions live in the docs, not in `CLAUDE.md` files, which stay short and point here. Read in this order before changing anything, and open only what your task needs:

1. [`doc/STATUS.md`](doc/STATUS.md): where we are, what is blocked.
2. [`doc/INDEX.md`](doc/INDEX.md): "How do I…?" router from a task to the exact doc and section.
3. [`doc/integration-plan.md`](doc/integration-plan.md): architecture (§1), contracts `ScrapedDocument` (§3) and `Finding` (§4), REST (§5), events (§6), conventions (§7), milestones (§8).
4. Your service's `CLAUDE.md` (table below), then its plan, for example [`doc/analytics-plan.md`](doc/analytics-plan.md).
5. [`openspec/specs/`](openspec/specs/) for what the system does now and [`openspec/changes/`](openspec/changes/) for what is in flight.
6. [`doc/decisions/`](doc/decisions/README.md) for why we chose X, so you don't relitigate it.

A doc claim that matters is checked against the code before you rely on it. After a change, update the docs with the `iw-docs-update` skill and run `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`; it fails on broken paths, an unlisted ADR, or a service without `CLAUDE.md`.

## Services

Three modules, three owners. The repository layout is defined by B; confirm before adding directories.

| Directory | Owner | Role | Rules |
|---|---|---|---|
| `scraper/` | A | collectors, queue, scheduler, `documents` writer | [`scraper/CLAUDE.md`](scraper/CLAUDE.md) |
| `analytics/` | C | modules M1-M3, rule engine, LLM layer | [`analytics/CLAUDE.md`](analytics/CLAUDE.md) |
| `api/` | C | REST, Socket.IO, migrations | [`api/CLAUDE.md`](api/CLAUDE.md) |
| `dashboard/` | B | frontend, alerts, calibration panel | [`dashboard/CLAUDE.md`](dashboard/CLAUDE.md) |
| `contracts/` | C | JSON Schema and mocks, frozen v1 | [`contracts/CLAUDE.md`](contracts/CLAUDE.md) |

## Process in one screen

Spec, then test, then code, then review, one PR per OpenSpec change (details: [`.claude/SDLC.md`](.claude/SDLC.md), review bar: [`.claude/CODE_REVIEW.md`](.claude/CODE_REVIEW.md)).

1. `iw-implement`: worktree + branch + `/openspec-propose`. Human approves the spec.
2. `/openspec-apply-change`; each commit goes through `iw-commit-cycle` (tdd-guide, code-reviewer on a pinned range, verify findings).
3. `iw-pr-review` before the PR; human go-ahead to push; then `/openspec-archive-change`, `iw-docs-update`, `iw-ai-log`.

## Hard rules

- No push, PR or merge without a fresh explicit go-ahead from the human. No `--force`, no amending a pushed commit, nothing straight to `main`.
- Contracts are frozen after Sat 14:30. Changing one needs the whole team and a version bump.
- Secrets only in untracked `.env` (`.env.example` is tracked). Never print proxy credentials or keys.
- No `console.log` / `print` debug output in committed code; JSON logs to stdout.
- Every dependency is scanned (`pip-audit` / `npm audit`) before merge.
- Verify every reviewer finding against the code before acting.
- ADRs in `doc/decisions/` are written by a human; agents may draft options, not the decision.

## Conventions

- Language: English for code, specs, ADRs, docs and `.claude/`; user-facing dashboard texts in Polish (team decision, [`doc/ai-workflow.md`](doc/ai-workflow.md)).
- Commits: Conventional Commits, terse subject. Branches: `scraper/*`, `analytics/*`, `dashboard/*`, `chore/*`. Worktrees live in `../InvestWatch-worktrees/`.
- Time is UTC ISO-8601, ids are UUID v4, config is env-only.
