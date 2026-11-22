# AI-Assisted Development Log

This log documents how the team builds InvestWatch with AI assistants (evaluation criterion: "standardized software development process with AI assistants", 20%). Add a short entry in [`ai-log/`](ai-log/README.md) at every milestone and whenever the process changes. Process detail: `../.claude/SDLC.md`, `../.claude/CODE_REVIEW.md`.

## Process

- **Spec-driven development with OpenSpec:** every change starts as a spec/proposal; implementation follows an approved spec.
- **Single source of truth:** the contracts in `contracts/` (JSON Schema) and the plans in `.docs/` are the context for both people and AI assistants.
- **Tools:** Claude Code (planning, code generation, review), OpenSpec (specs and change proposals).
- **Review rules for generated code:** every AI-generated change is read by a human before merge; no secrets in prompts or commits; dependencies added by AI are checked with `npm audit` / `pip-audit`.
- **Language:** technical documentation, code and commit messages in English; user-facing texts in Polish.

## Context the agents get

| Layer | File | Purpose |
|---|---|---|
| Project | `CLAUDE.md` | process, hard rules, conventions |
| Service | `<service>/CLAUDE.md` (e.g. `scraper/`) | stack, definition of done |
| Contracts | `integration-plan.md`, `contracts/` | source of truth for data shapes |
| Behaviour | `openspec/specs/`, `openspec/changes/` | what exists, what is changing |
| Decisions | `decisions/` | why, so agents don't relitigate |
| State | `STATUS.md`, `status/` | milestones and team-wide blockers; one file per domain for module state |
| Agent | `.claude/agents/iw-reviewer.md` | read-only reviewer used by the skills below |
| Skills | `.claude/skills/` | `iw-implement`, `iw-commit-cycle`, `iw-pr-review`, `iw-docs-update`, `iw-ai-log`, `iw-scraper-conventions`, `iw-watch`, plus the OpenSpec skills |

All of it is committed, so the three of us run identical agents. The AI assistants are a development tool only: the product runs on local open-source models (Ollama).

## Lifecycle of one change

Intake (docs first, STATUS) → `iw-implement` (size, worktree) → `/openspec-propose`, human approves → `/openspec-apply-change` with `iw-commit-cycle` per task group → closing tasks (docs, log entry, whole-branch review) → `/openspec-archive-change` as the last commit → agent pushes and opens the PR → human approves and merges. Canonical stages and gates: `../.claude/SDLC.md`.

## Controls on generated code

- **Spec before code** for each capability (one OpenSpec change holds many tasks); `openspec validate --strict` before commit. A hook refuses service-code commits with no active change.
- **Tests first**, and a test must be able to fail: the test names the production change that turns it red.
- **Review per task group with logic** by the shipped read-only `iw-reviewer` agent on that group's own pinned range (`GROUP_BASE..HEAD`), then one whole-branch pass before the PR that looks for cross-group and spec gaps. The reviewer reports only verified blocking defects in the range (a concrete trigger each, no nits or style); a security focus is folded into the same pass. Every finding is verified against the code before it is acted on; false ones are rejected with evidence.
- **Deterministic guards**, not prompts: a tested hook denies force push, any push to `main`, amending pushed commits, and on commit a staged `.env`, `console.log` in JS/TS, and service code without an active change. Pushes and PR creation also require approval (`permissions.ask`).
- **Human gates**: spec approval, and PR approval and merge. The agent pushes its own branch and opens the PR once the PR-ready criteria hold ([ADR 0207](decisions/0207-agent-push-and-pr.md)). ADRs are agent-written, committed as accepted, and take effect when the human approves and merges the PR.
- **Agent-to-agent hand-offs** (`iw-watch`): each teammate's watcher polls GitHub and hands an item to an agent once: a review on my PR (fix, answer or ask me, push, reply), a review request (review as a comment), a defect in someone else's path (an issue assigned to its CODEOWNERS owner). A deterministic runner decides what and when; the headless session gets an allow-list built for that one item, review text is fenced as data and only from collaborators, a PR under review is never checked out, and a marker in every agent comment caps the rounds at 3, so two watchers cannot ping-pong. Approval and merge stay human.
- **Supply chain**: `pip-audit` / `npm audit` before merge (and via the manual CI workflow before milestones); secrets only in untracked `.env`.
- **Untrusted content**: scraped text is data. It is delimited, length-limited and never executed or used to pick a fetch target (prompt-injection and SSRF defence).
- **Optional**: a second reviewer from a different model family on high-risk diffs (contracts, credentials).

Known limits: review is a practice, not enforced by a hook; the hook reads only the staged diff (stage and commit in separate calls) and its escape flags are plain text, so it catches mistakes, not a determined agent; the second-family reviewer is not set up; this log is hand-appended (skill `iw-ai-log`); CI is manual-only for now.

## Log

One file per entry in [`ai-log/`](ai-log/README.md), named `YYYY-MM-DDTHHMM-<who>-<slug>.md`, so the listing reads in time order and parallel PRs never edit the same file ([ADR 0212](decisions/0212-ai-log-one-file-per-entry.md)). How to add one: the `iw-ai-log` skill. The whole log as one table, oldest first:

```sh
node .claude/skills/iw-ai-log/scripts/ai-log.mjs render
```
