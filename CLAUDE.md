# InvestWatch

Hackathon system (HackNation, UKNF challenge) that finds risky investment content online. Lightweight separate services, one `docker compose up`, open-source and on-premise, with one mentor-approved exception: the LLM may be a hosted model if it swaps to a local open model (Gemma via Ollama) by env only ([ADR 0304](.docs/decisions/0304-llm-serving.md)). Hand-in: Sun 2026-11-22, 10:30.

## Docs first

Business logic, contracts and decisions live in the docs, not in `CLAUDE.md` files, which stay short and point here. Read in this order before changing anything, and open only what your task needs:

1. [`.docs/STATUS.md`](.docs/STATUS.md): milestones and team-wide blockers, then the file of your domain in [`.docs/status/`](.docs/status/) (`scraper`, `dashboard`, `platform`): where we are, what is blocked.
2. [`.docs/INDEX.md`](.docs/INDEX.md): "How do I…?" router from a task to the exact doc and section.
3. [`.docs/integration-plan.md`](.docs/integration-plan.md): architecture (§1), contracts `ScrapedDocument` (§3) and `Finding` (§4), REST (§5), events (§6), conventions (§7), milestones (§8).
4. Your service's `CLAUDE.md` (table below), then its plan, for example [`.docs/analytics-plan.md`](.docs/analytics-plan.md).
5. [`openspec/specs/`](openspec/specs/) for what the system does now and [`openspec/changes/`](openspec/changes/) for what is in flight.
6. [`.docs/decisions/`](.docs/decisions/README.md) for why we chose X, so you don't relitigate it.

A doc claim that matters is checked against the code before you rely on it. After a change, update the docs with the `iw-docs-update` skill and run `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`; it fails on broken paths, an unlisted ADR, or a service without `CLAUDE.md`.

## Services

Three modules, three owners. Kacper defined the repository layout (root [`README.md`](README.md) has the human-facing overview and Quick Start); confirm with Kacper before adding directories. Each service has a `README.md` (people, jury) and a `CLAUDE.md` (agents).

| Directory | Owner | Role | Rules |
|---|---|---|---|
| `scraper/` | Adam | collectors, queue, scheduler, `documents` writer | [`scraper/CLAUDE.md`](scraper/CLAUDE.md) |
| `analytics/` | Damian | modules M1-M3, rule engine, LLM layer | [`analytics/CLAUDE.md`](analytics/CLAUDE.md) |
| `web/` | Kacper | frontend, alerts, calibration panel | [`web/CLAUDE.md`](web/CLAUDE.md) |
| `contracts/` | Damian | JSON Schemas, OpenAPI, mocks, validator (draft v1) | [`contracts/CLAUDE.md`](contracts/CLAUDE.md) |
| `api/` | Damian | shared database schema (Alembic), REST API, Socket.IO gateway | [`api/CLAUDE.md`](api/CLAUDE.md) |
| `infra/` | Kacper | shared infrastructure: Postgres, Redis, object storage (MinIO), optional Ollama (`--profile llm`), HTTPS gateway; root `compose.yaml` includes each module's file | [`infra/CLAUDE.md`](infra/CLAUDE.md) |

`api/` (Damian) was added by the `api-db-schema` change as ADR 0302 planned; every new service directory gets a `CLAUDE.md` first, and `docs-check` enforces it.

## Process in one line

OpenSpec drives implementation: `iw-implement` (size, worktree) → `/openspec-propose` (human approves) → `/openspec-apply-change` with `iw-commit-cycle` per task group → closing tasks (`iw-docs-update`, `iw-ai-log`, `iw-pr-review`) → `/openspec-archive-change` as the last commit → the agent pushes the branch and opens the PR → the human approves and merges. Stages, gates and who owns which fact: [`.claude/SDLC.md`](.claude/SDLC.md). Review criteria: [`.claude/CODE_REVIEW.md`](.claude/CODE_REVIEW.md). The reviewer agent `iw-reviewer` and the hook are in `.claude/`.

## Setup (once per teammate)

- **Node >= 22.20** on PATH (the hook and OpenSpec need it) and git with symlink support: the OpenSpec skills are symlinks (Windows: `git config --global core.symlinks true`, or use WSL).
- **OpenSpec CLI**, pinned like CI: `npm i -g @fission-ai/openspec@2.1.1`, then `openspec --version`. Optional telemetry opt-out: `OPENSPEC_TELEMETRY=0`. The OpenSpec skills call this command and fail without it.
- **Claude Code opened inside the repo or a worktree** so `.claude/` loads (skills, the `iw-reviewer` agent, the git hook, push permissions). The ECC plugin is optional; nothing here depends on it.
- `gh` logged in. Per-module tooling is in that module's `CLAUDE.md`.

## Hard rules

- An agent may push its own branch to `origin` and open a PR in this repository without asking, once the PR-ready criteria in [`.claude/CODE_REVIEW.md`](.claude/CODE_REVIEW.md) hold ([ADR 0207](.docs/decisions/0207-agent-push-and-pr.md)). The human approves and merges every PR: an agent never merges, never approves, never marks a PR ready for someone else. No `--force`, no amending a pushed commit, nothing straight to `main`. The hook also denies another remote, deleting or updating any branch but the current one, rewiring a remote, and merging or approving through `gh api`; it reads command text only and is a guard against mistakes, not a security boundary (ADR 0207).
- Contracts are frozen after Sat 14:30 (hook-enforced; escape `IW_CONTRACT_CHANGE=1`). Changing one needs the whole team and a version bump. Exception until Integration #1 (Sat 17:00): non-required fields are provisional and change without a bump, in a PR reviewed by their consumers ([ADR 0301](.docs/decisions/0301-contracts-v1.md)).
- Secrets only in untracked `.env` (`.env.example` is tracked). Never print proxy credentials or keys.
- No `console.log` in committed JS/TS (hook-enforced); Python uses the logger, not `print`; JSON logs to stdout.
- Stage and commit in separate tool calls. Never use an `IW_*` escape flag without telling the human.
- Every dependency is scanned (`pip-audit` / `npm audit`) before merge.
- Before any PR is opened, docs and specs are already updated in the same PR: the OpenSpec change and its deltas (archived as the last commit), the affected docs, ADRs, your own domain file in `.docs/status/` (only yours; `.docs/STATUS.md` only when a milestone or a team-wide decision changes), the AI log entry (`.docs/ai-log/`), and `docs-check` clean. Never open a PR with these "to follow".
- Verify every reviewer finding against the code before acting.
- ADRs in `.docs/decisions/` are written by agents, in the same PR as the change they record, or in an earlier docs-only PR when the decision steers work still to come (the implementing PR then links the ADR): context, options with evidence, the decision and a rationale that cites that evidence (never an invented "why"). Committed with `Status: accepted`, effective when the human approves and merges the PR (a rejected ADR is changed or removed in review).

## Conventions

- Language: English for code, specs, ADRs, docs and `.claude/`; user-facing dashboard texts in Polish (team decision, [`.docs/ai-workflow.md`](.docs/ai-workflow.md)).
- Commits: Conventional Commits, terse subject. Branches: `scraper/*`, `analytics/*`, `web/*`, `api/*`, `contracts/*`, `chore/*`. Worktrees live in `../InvestWatch-worktrees/`.
- Time is UTC ISO-8601, ids are UUID v4, config is env-only.
