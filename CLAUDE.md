# InvestWatch

Hackathon system (HackNation, UKNF challenge) that finds risky investment content online. Lightweight separate services, one `docker compose up`, open-source and on-premise only (no paid APIs at runtime). Hand-in: Sun 2026-11-22, 10:30.

## Docs first

Business logic, contracts and decisions live in the docs, not in `CLAUDE.md` files, which stay short and point here. Read in this order before changing anything, and open only what your task needs:

1. [`.docs/STATUS.md`](.docs/STATUS.md): where we are, what is blocked.
2. [`.docs/INDEX.md`](.docs/INDEX.md): "How do I…?" router from a task to the exact doc and section.
3. [`.docs/integration-plan.md`](.docs/integration-plan.md): architecture (§1), contracts `ScrapedDocument` (§3) and `Finding` (§4), REST (§5), events (§6), conventions (§7), milestones (§8).
4. Your service's `CLAUDE.md` (table below), then its plan, for example [`.docs/analytics-plan.md`](.docs/analytics-plan.md).
5. [`openspec/specs/`](openspec/specs/) for what the system does now and [`openspec/changes/`](openspec/changes/) for what is in flight.
6. [`.docs/decisions/`](.docs/decisions/README.md) for why we chose X, so you don't relitigate it.

A doc claim that matters is checked against the code before you rely on it. After a change, update the docs with the `iw-docs-update` skill and run `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`; it fails on broken paths, an unlisted ADR, or a service without `CLAUDE.md`.

## Services

Three modules, three owners. B defined the repository layout (root [`README.md`](README.md) has the human-facing overview and Quick Start); confirm with B before adding directories. Each service has a `README.md` (people, jury) and a `CLAUDE.md` (agents).

| Directory | Owner | Role | Rules |
|---|---|---|---|
| `scraper/` | A | collectors, queue, scheduler, `documents` writer | [`scraper/CLAUDE.md`](scraper/CLAUDE.md) |
| `analytics/` | C | modules M1-M3, rule engine, LLM layer | [`analytics/CLAUDE.md`](analytics/CLAUDE.md) |
| `web/` | B | frontend, alerts, calibration panel | [`web/CLAUDE.md`](web/CLAUDE.md) |

`api/` and `contracts/` (C) appear in the integration plan but not in B's layout yet. Whoever creates them adds a `CLAUDE.md` first; `docs-check` enforces it.

## Process in one line

OpenSpec drives implementation: `iw-implement` (size, worktree) → `/openspec-propose` (human approves) → `/openspec-apply-change` with `iw-commit-cycle` per task group → closing tasks (`iw-docs-update`, `iw-ai-log`, `iw-pr-review`) → `/openspec-archive-change` as the last commit → the human pushes. Stages, gates and who owns which fact: [`.claude/SDLC.md`](.claude/SDLC.md). Review criteria: [`.claude/CODE_REVIEW.md`](.claude/CODE_REVIEW.md). The reviewer agent `iw-reviewer` and the hook are in `.claude/`.

## Setup (once per teammate)

- **Node >= 22.20** on PATH (the hook and OpenSpec need it) and git with symlink support: the OpenSpec skills are symlinks (Windows: `git config --global core.symlinks true`, or use WSL).
- **OpenSpec CLI**, pinned like CI: `npm i -g @fission-ai/openspec@2.1.1`, then `openspec --version`. Optional telemetry opt-out: `OPENSPEC_TELEMETRY=0`. The OpenSpec skills call this command and fail without it.
- **Claude Code opened inside the repo or a worktree** so `.claude/` loads (skills, the `iw-reviewer` agent, the git hook, push permissions). The ECC plugin is optional; nothing here depends on it.
- `gh` logged in. Per-module tooling is in that module's `CLAUDE.md`.

## Hard rules

- No push, PR or merge without a fresh explicit go-ahead from the human. No `--force`, no amending a pushed commit, nothing straight to `main`.
- Contracts are frozen after Sat 14:30. Changing one needs the whole team and a version bump.
- Secrets only in untracked `.env` (`.env.example` is tracked). Never print proxy credentials or keys.
- No `console.log` in committed JS/TS (hook-enforced); Python uses the logger, not `print`; JSON logs to stdout.
- Stage and commit in separate tool calls. Never use an `IW_*` escape flag without telling the human.
- Every dependency is scanned (`pip-audit` / `npm audit`) before merge.
- Verify every reviewer finding against the code before acting.
- ADRs in `.docs/decisions/` are written by a human; agents may draft options, not the decision.

## Conventions

- Language: English for code, specs, ADRs, docs and `.claude/`; user-facing dashboard texts in Polish (team decision, [`.docs/ai-workflow.md`](.docs/ai-workflow.md)).
- Commits: Conventional Commits, terse subject. Branches: `scraper/*`, `analytics/*`, `web/*`, `api/*`, `contracts/*`, `chore/*`. Worktrees live in `../InvestWatch-worktrees/`.
- Time is UTC ISO-8601, ids are UUID v4, config is env-only.
