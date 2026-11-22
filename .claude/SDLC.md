# InvestWatch SDLC

How the three of us ship with Claude Code. Adapted from the Neopadel pilot, cut down for a 24-hour hackathon and fully git-tracked, so every teammate gets the same skills, agent and hook. **OpenSpec drives implementation**; the `iw-*` skills attach to defined points in it. The jury-facing summary and the AI log are in `.docs/ai-workflow.md`.

## Who owns which fact (edit the owner, link from elsewhere)

| Fact | Lives in |
|---|---|
| Hard rules (push, secrets, contracts) | `CLAUDE.md` |
| Stage order, gates, which skill when | this file |
| Sizing: when a spec is needed | `.claude/skills/iw-implement/SKILL.md` |
| Per-task-group loop: test, commit, review | `.claude/skills/iw-commit-cycle/SKILL.md` |
| Review criteria ("ready") | `.claude/CODE_REVIEW.md` |
| Review commands, PR body | `.claude/skills/iw-pr-review/SKILL.md` |
| Which doc to update, ADRs, closing a change | `.claude/skills/iw-docs-update/SKILL.md` |
| AI log row | `.claude/skills/iw-ai-log/SKILL.md` |
| Agent hand-offs: watching GitHub for reviews, review requests, owner-routed issues | `.claude/skills/iw-watch/SKILL.md` |
| Hook behaviour and escapes | header of `.claude/hooks/git-guard.js` |
| Closing tasks and apply/archive guidance | `openspec/config.yaml` |
| Docs map | `.docs/INDEX.md` |
| Behaviour now / in flight | `openspec/specs/`, `openspec/changes/` |

## Stages

| # | Stage | Tool | Gate |
|---|---|---|---|
| 0 | Intake: docs first (`CLAUDE.md`), `.docs/STATUS.md` and the `.docs/status/` file for your directories, the owning spec | agent | none |
| 1 | Size, worktree, branch | `iw-implement` | branch prefix = module |
| 2 | Explore (only if scope is foggy) | `/openspec-explore` | none |
| 3 | Spec | `/openspec-propose` | human approves; `openspec validate --strict` |
| 4 | Implement, per task group | `/openspec-apply-change` + `iw-commit-cycle` | failing test first, mutation check per task group; `iw-reviewer` on each logic group's own range |
| 5 | Closing tasks (generated into every `tasks.md`) | `iw-docs-update`, `iw-ai-log`, `iw-pr-review` | docs-check clean, review findings verified |
| 6 | Archive, as the last commit of the branch | `/openspec-archive-change` | specs updated |
| 7 | Push the branch and open the PR | agent | PR-ready criteria in `.claude/CODE_REVIEW.md`; `origin` and the current branch only, never `main`, never `--force` (hook); the PR body lists every `IW_*` escape used and says that it loosens no permission beyond ADR 0207 |
| 7b | Approve and merge | human | review, approval and merge are always the human's (`gh pr merge`, `gh pr ready` and `gh pr review` stay in `permissions.ask`; the hook denies `gh api` merge and approve calls) |
| 7c | Hand-offs between teammates' agents (optional) | `iw-watch`: `/loop 2m /iw-watch --mine` in a session, or `watch.mjs run` from launchd or cron | headless sessions run sandboxed and publish nothing; the runner checks their commits and pushes that PR's branch and one comment, only with `--publish` (ADR 0210); never approve or merge, stop at 3 rounds per PR and hand over to the human |
| 8 | CI (advisory for now) | `.github/workflows/ci.yml`, manual dispatch | not a merge gate during the hackathon; becomes a required check in the full SDLC |
| 9 | After merge | remove the worktree | nothing else: docs, log and archive were in the PR |

## Deterministic guards (`git-guard.js`, tested)

Denies force push, any push to `main` (including `HEAD` and full refs), `--all`/`--mirror`, `reset --hard`, whole-tree checkout, amending a pushed commit, and a `git add` chained in front of a commit; on commit denies a staged `.env`, `console.log` in non-test JS/TS, service code with no active OpenSpec change, and (from Sat 14:30) any change to `contracts/schemas`, `contracts/mocks` or `contracts/openapi.yaml` (escape `IW_CONTRACT_CHANGE=1`, only with the whole team's agreement and a version bump). It reads the staged diff at command start, so stage and commit in separate calls. Its escapes are plain text an agent can write: it catches mistakes, not a determined agent, so any use of an `IW_*` escape is reported in the PR body.

## Findings triage

Anything real but out of scope goes into the change's `follow-ups.md` with one disposition: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`. No row stays unresolved when the PR is opened.

## Parallel work

Three people, a worktree per change, ownership by directory in [`.github/CODEOWNERS`](../.github/CODEOWNERS) (the only place that names owners; shared areas have none, [ADR 0211](../.docs/decisions/0211-codeowners-single-source.md)). To limit merge conflicts: edit only the `.docs/status/` file for the directories you changed (`.docs/STATUS.md` is team-wide only, [ADR 0205](../.docs/decisions/0205-status-per-domain.md)); ADR numbers by owner (A 01xx, Kacper 02xx, Damian 03xx); the AI log table merges by keeping both sides' rows. Touching a directory someone else owns in `CODEOWNERS`, or a frozen contract, is announced in the team chat first.

## Not adopted from Neopadel (on purpose)

Mutation-testing tooling (only the manual mutate-and-restore check in `iw-commit-cycle` is adopted), the LLM-judge hook, receipt gates, retro and memory audits, Monday sync. Revisit after the hackathon if the process continues.

## Kill switch

Rename a `.claude/skills/<name>` directory (append `.disabled`), delete `.claude/agents/iw-reviewer.md`, or remove an entry from `.claude/settings.json` to disable one automation, and say so in the team chat.
