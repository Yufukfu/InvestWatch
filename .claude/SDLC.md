# InvestWatch SDLC

How the three of us ship with Claude Code. Adapted from the Neopadel pilot, cut down for a 24-hour hackathon and fully git-tracked so every teammate gets the same skills and hooks. The process narrative and its evidence (a Log table appended via `iw-ai-log`) live in `doc/ai-workflow.md`.

## Where things live

| Question | Place |
|---|---|
| What does the system do now? | `openspec/specs/` (updated on archive) |
| What are we changing right now? | `openspec/changes/<slug>/` (proposal, specs delta, design, tasks, `follow-ups.md`) |
| Why did we choose X? | `doc/decisions/` (ADRs, human-authored) |
| Where are we, what is blocked? | `doc/STATUS.md` |
| Contracts and architecture | `doc/integration-plan.md`, later `contracts/` |

## Stages

| # | Stage | Tool | Gate |
|---|---|---|---|
| 0 | Intake: read `doc/STATUS.md` and the owning spec | agent | none |
| 1 | Size: trivial fix vs. spec'd change; foggy scope goes to `/openspec-explore` | human | none |
| 2 | Worktree + branch | `iw-implement` | branch prefix per module |
| 3 | Spec | `/openspec-propose` | human approves; `openspec validate --strict` |
| 4 | Implement per commit | `/openspec-apply-change`, `iw-commit-cycle` | failing test first; tdd-guide; code-reviewer on pinned range |
| 5 | Whole-branch check | `iw-pr-review` | deterministic checks green, findings verified |
| 6 | Push and PR | human | fresh go-ahead, every time |
| 7 | CI (advisory for now) | `.github/workflows/ci.yml`, manual dispatch | not a merge gate during the hackathon; becomes a required check in the full SDLC; meanwhile run it before milestones and hand-in for a recorded dependency audit |
| 8 | After merge | `/openspec-archive-change`, `iw-docs-update` (incl. `doc/STATUS.md`), `iw-ai-log` | specs updated, log entry added |

Sizing: **one OpenSpec change per capability, not per task.** A change such as `scraper-v1` or `scraper-social-collectors` holds many tasks in its `tasks.md` and many commits, and one active change satisfies the commit hook for all of them. Adding a source or a parser to an existing capability, bug fixes, one-file fixes and docs need no new change (`IW_SKIP_SPEC=1` on the commit if none is active). A contract, a cross-module or a security-relevant change always gets one.

## Deterministic guards (`.claude/hooks/git-guard.js`, tested)

Denies force push, push to `main`, `reset --hard`, whole-tree checkout, amending a pushed commit; on commit denies a staged `.env`, `console.log` in non-test JS/TS, and service code with no active OpenSpec change. Escapes are named in the hook header and need the human's say-so.

## Findings triage

Anything real but out of scope goes into the change's `follow-ups.md` with one disposition: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`. No row stays unresolved at merge.

## Parallel work

Three people, three modules, so a worktree per change and ownership by directory (`scraper/` A, `dashboard/` B, `analytics/` `api/` `contracts/` C). Touching another owner's directory or a frozen contract is announced in the team chat first.

## Not adopted from Neopadel (on purpose)

Mutation testing, the LLM-judge hook, receipt gates, retro and memory audits, Monday sync. Revisit after the hackathon if the process continues.

## Kill switch

Rename a `.claude/skills/<name>` directory (append `.disabled`) or remove its entry from `.claude/settings.json` to disable one automation, and say so in the team chat.
