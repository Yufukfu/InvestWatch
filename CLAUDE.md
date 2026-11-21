# InvestWatch

Hackathon system (HackNation, UKNF challenge) that finds risky investment content online. Three modules, three owners: **scraper** (A), **dashboard** (B), **analytics + api + contracts** (C). Hand-in: Sun 2026-11-22, 10:30.

Lightweight separate services, one `docker compose up`, open-source and on-premise only (no paid APIs at runtime).

## Read first

- `doc/STATUS.md`: where we are, what is blocked. Update it when a milestone moves.
- `doc/integration-plan.md`: architecture, contracts v1 (`ScrapedDocument`, `Finding`), REST and events.
- `doc/INDEX.md`: map of everything else. `.claude/SDLC.md`: the process. Per-service `CLAUDE.md` before touching that service.

## Process in one screen

Spec, then test, then code, then review, one PR per OpenSpec change (details: `.claude/SDLC.md`).

1. `iw-implement`: worktree + branch + `/openspec-propose`. Human approves the spec.
2. `/openspec-apply-change`; each commit goes through `iw-commit-cycle` (tdd-guide, code-reviewer on a pinned range, verify findings).
3. `iw-pr-review` before the PR; human go-ahead to push; then `/openspec-archive-change`, `doc/STATUS.md`, `iw-ai-log`.

## Hard rules

- No push, PR or merge without a fresh explicit go-ahead from the human. No `--force`, no amending a pushed commit, nothing straight to `main`.
- Contracts are frozen after Sat 14:30. Changing one needs the whole team and a version bump.
- Secrets only in untracked `.env` (`.env.example` is tracked). Never print proxy credentials or keys.
- No `console.log` / `print` debug output in committed code; JSON logs to stdout.
- Every dependency is scanned (`pip-audit` / `npm audit`) before merge.
- Verify every reviewer finding against the code before acting. Don't trust a doc claim without checking the code.
- ADRs in `doc/decisions/` are written by a human; agents may draft options, not the decision.

## Conventions

- Language: English for code, specs, ADRs, docs and `.claude/`; user-facing dashboard texts in Polish (team decision, `doc/ai-workflow.md`).
- Commits: Conventional Commits, terse subject. Branches: `scraper/*`, `analytics/*`, `dashboard/*`, `chore/*`. Worktrees live in `../InvestWatch-worktrees/`.
- Time is UTC ISO-8601, ids are UUID v4, config is env-only.
