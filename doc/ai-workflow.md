# AI-assisted workflow

How we build InvestWatch with AI assistants, and the controls that keep generated code trustworthy. Evidence: `ai-log.md`. Process detail: `../.claude/SDLC.md`, `../.claude/CODE_REVIEW.md`.

## Tools

- **Claude Code** for implementation and review, one session per task, in its own git worktree.
- **OpenSpec** (spec-driven development): every non-trivial task has a proposal, requirement scenarios, a design and a task list before code exists, and the validated specs become the system's documented behaviour on archive.
- **Local open-source models** (Ollama) inside the product only. AI assistants are a development tool, not a runtime dependency.

## Context the agents get

| Layer | File | Purpose |
|---|---|---|
| Project | `CLAUDE.md` | process, hard rules, conventions |
| Service | `scraper/CLAUDE.md` (one per service) | stack, definition of done |
| Contracts | `plan-integracji.md`, `contracts/` | source of truth for data shapes |
| Behaviour | `openspec/specs/`, `openspec/changes/` | what exists, what is changing |
| Decisions | `decisions/` | why, so agents don't relitigate |
| State | `STATUS.md` | milestone and blockers |
| Skills | `.claude/skills/` | `iw-implement`, `iw-commit-cycle`, `iw-pr-review`, `iw-ai-log`, `iw-scraper-conventions`, plus the OpenSpec skills |

All of it is committed, so the three of us run identical agents.

## Lifecycle of one change

Intake (STATUS, owning spec) → worktree and branch → OpenSpec proposal, human approves → failing test → implementation → per-commit review → whole-branch review → human go-ahead → PR and CI → archive, STATUS, log entry.

## Controls on generated code

- **Spec before code** for each capability (one OpenSpec change holds many tasks); `openspec validate --strict` before commit. A hook refuses service-code commits with no active change.
- **Tests first**, and a test must be able to fail: the test names the production change that turns it red.
- **Per-commit review** by a fresh reviewer agent on a pinned `merge-base..HEAD` range, checking plan compliance, then a whole-branch review before the PR. Every finding is verified against the code before it is acted on, false ones are rejected with evidence.
- **Deterministic guards**, not prompts: hook-enforced bans on force push, pushes to `main`, amending pushed commits, staged `.env` files and `console.log`.
- **Human gates**: spec approval, and a fresh go-ahead for every push and PR. ADRs are human-written.
- **Supply chain**: `pip-audit` / `npm audit` before merge (and via the manual CI workflow before milestones); secrets only in untracked `.env`.
- **Untrusted content**: scraped text is data. It is delimited, length-limited and never executed or used to pick a fetch target (prompt-injection and SSRF defence).
- **Optional**: a second reviewer from a different model family on high-risk diffs (contracts, credentials).

## Example prompts that worked

Add real, redacted excerpts here from `ai-log.md` at each milestone. Placeholders are worse than nothing, so the list stays empty until there is a real prompt to show.

## Known limits

Per-commit review is a practice, not enforced by a hook; the second-family reviewer is not set up; the AI log is hand-appended.
