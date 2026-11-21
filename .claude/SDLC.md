# InvestWatch SDLC

How the three of us ship with Claude Code. Adapted from the Neopadel pilot, cut down for a 24-hour hackathon and fully git-tracked, so every teammate gets the same skills, agent and hook. **OpenSpec drives implementation**; the `iw-*` skills attach to defined points in it. The jury-facing summary and the AI log are in `.docs/ai-workflow.md`.

## Who owns which fact (edit the owner, link from elsewhere)

| Fact | Owner |
|---|---|
| Hard rules (push, secrets, contracts) | `CLAUDE.md` |
| Stage order, gates, which skill when | this file |
| Sizing: when a spec is needed | `.claude/skills/iw-implement/SKILL.md` |
| Per-task-group loop: test, commit, review | `.claude/skills/iw-commit-cycle/SKILL.md` |
| Review criteria ("ready") | `.claude/CODE_REVIEW.md` |
| Review commands, PR body | `.claude/skills/iw-pr-review/SKILL.md` |
| Which doc to update, ADRs, closing a change | `.claude/skills/iw-docs-update/SKILL.md` |
| AI log row | `.claude/skills/iw-ai-log/SKILL.md` |
| Hook behaviour and escapes | header of `.claude/hooks/git-guard.js` |
| Closing tasks and apply/archive guidance | `openspec/config.yaml` |
| Docs map | `.docs/INDEX.md` |
| Behaviour now / in flight | `openspec/specs/`, `openspec/changes/` |

## Stages

| # | Stage | Tool | Gate |
|---|---|---|---|
| 0 | Intake: docs first (`CLAUDE.md`), `.docs/STATUS.md`, the owning spec | agent | none |
| 1 | Size, worktree, branch | `iw-implement` | branch prefix = module |
| 2 | Explore (only if scope is foggy) | `/openspec-explore` | none |
| 3 | Spec | `/openspec-propose` | human approves; `openspec validate --strict` |
| 4 | Implement, per task group | `/openspec-apply-change` + `iw-commit-cycle` | failing test first; `iw-reviewer` per task group or before a push |
| 5 | Closing tasks (generated into every `tasks.md`) | `iw-docs-update`, `iw-ai-log`, `iw-pr-review` | docs-check clean, review findings verified |
| 6 | Archive, as the last commit of the branch | `/openspec-archive-change` | specs updated |
| 7 | Push and PR | human | fresh go-ahead every time (also `permissions.ask`) |
| 8 | CI (advisory for now) | `.github/workflows/ci.yml`, manual dispatch | not a merge gate during the hackathon; becomes a required check in the full SDLC |
| 9 | After merge | remove the worktree | nothing else: docs, log and archive were in the PR |

## Deterministic guards (`git-guard.js`, tested)

Denies force push, any push to `main` (including `HEAD` and full refs), `--all`/`--mirror`, `reset --hard`, whole-tree checkout, amending a pushed commit, and a `git add` chained in front of a commit; on commit denies a staged `.env`, `console.log` in non-test JS/TS, and service code with no active OpenSpec change. It reads the staged diff at command start, so stage and commit in separate calls. Its escapes are plain text an agent can write: it catches mistakes, not a determined agent, so any use of an `IW_*` escape is reported in the PR body.

## Findings triage

Anything real but out of scope goes into the change's `follow-ups.md` with one disposition: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`. No row stays unresolved when the PR is opened.

## Parallel work

Three people, three modules, a worktree per change, ownership by directory (`scraper/` A, `web/` B, `analytics/` C, plus `api/` and `contracts/` C once created). To limit merge conflicts: edit only your own row in `.docs/STATUS.md`; ADR numbers by owner (A 01xx, B 02xx, C 03xx); the AI log table merges by keeping both sides' rows. Touching another owner's directory or a frozen contract is announced in the team chat first.

## Not adopted from Neopadel (on purpose)

Mutation testing, the LLM-judge hook, receipt gates, retro and memory audits, Monday sync. Revisit after the hackathon if the process continues.

## Kill switch

Rename a `.claude/skills/<name>` directory (append `.disabled`), delete `.claude/agents/iw-reviewer.md`, or remove an entry from `.claude/settings.json` to disable one automation, and say so in the team chat.
