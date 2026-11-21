# AI-Assisted Development Log

This log documents how the team builds InvestWatch with AI assistants (evaluation criterion: "standardized software development process with AI assistants", 20%). Add a short entry at every milestone and whenever the process changes. Process detail: `../.claude/SDLC.md`, `../.claude/CODE_REVIEW.md`.

## Process

- **Spec-driven development with OpenSpec:** every change starts as a spec/proposal; implementation follows an approved spec.
- **Single source of truth:** the contracts in `contracts/` (JSON Schema) and the plans in `doc/` are the context for both people and AI assistants.
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
| State | `STATUS.md` | milestone and blockers |
| Skills | `.claude/skills/` | `iw-implement`, `iw-commit-cycle`, `iw-pr-review`, `iw-ai-log`, `iw-scraper-conventions`, plus the OpenSpec skills |

All of it is committed, so the three of us run identical agents. The AI assistants are a development tool only: the product runs on local open-source models (Ollama).

## Lifecycle of one change

Intake (STATUS, owning spec) → worktree and branch → OpenSpec proposal, human approves → failing test → implementation → per-commit review → whole-branch review → human go-ahead → PR → archive, STATUS, log entry.

## Controls on generated code

- **Spec before code** for each capability (one OpenSpec change holds many tasks); `openspec validate --strict` before commit. A hook refuses service-code commits with no active change.
- **Tests first**, and a test must be able to fail: the test names the production change that turns it red.
- **Per-commit review** by a fresh reviewer agent on a pinned `merge-base..HEAD` range, checking plan compliance, then a whole-branch review before the PR. Every finding is verified against the code before it is acted on; false ones are rejected with evidence.
- **Deterministic guards**, not prompts: hook-enforced bans on force push, pushes to `main`, amending pushed commits, staged `.env` files and `console.log`.
- **Human gates**: spec approval, and a fresh go-ahead for every push and PR. ADRs are human-written.
- **Supply chain**: `pip-audit` / `npm audit` before merge (and via the manual CI workflow before milestones); secrets only in untracked `.env`.
- **Untrusted content**: scraped text is data. It is delimited, length-limited and never executed or used to pick a fetch target (prompt-injection and SSRF defence).
- **Optional**: a second reviewer from a different model family on high-risk diffs (contracts, credentials).

Known limits: per-commit review is a practice, not enforced by a hook; the second-family reviewer is not set up; this log is hand-appended (skill `iw-ai-log`). CI is manual-only for now.

## Log

| When | Who | What was done with AI | Outcome / lesson |
|---|---|---|---|
| Sat 11:15 | C | Read all 16 HackNation tasks and compared the top candidates (scope, criteria, constraints) | Team picked #InvestWatch |
| Sat 13:00 | C | Summarized the UKNF task, rules and annexes (18 risk-information rules, registry links, advisory definition) | Requirements in one place |
| Sat 13:40 | C | Drafted the integration plan (contracts, REST/WS API, milestones) and the analytics work plan | `doc/integration-plan.md`, `doc/analytics-plan.md` |
| Sat 14:10 | C | Applied team sync decisions; translated technical docs to English; started this log | English docs; OpenSpec adopted |
| Sat ~13:50 | A | Had Claude Code adapt the Neopadel SDLC (keep/leave table first): OpenSpec, `iw-*` skills, a tested `git-guard` hook, SDLC and review docs | PR #1. A first hook draft would have blocked committing `scraper/CLAUDE.md` (markdown counted as service code); caught while checking what the PR commits, fixed and pinned with a test |
