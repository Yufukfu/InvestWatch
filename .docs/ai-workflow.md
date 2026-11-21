# AI-Assisted Development Log

This log documents how the team builds InvestWatch with AI assistants (evaluation criterion: "standardized software development process with AI assistants", 20%). Add a short entry at every milestone and whenever the process changes. Process detail: `../.claude/SDLC.md`, `../.claude/CODE_REVIEW.md`.

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
| State | `STATUS.md` | milestone and blockers |
| Agent | `.claude/agents/iw-reviewer.md` | read-only reviewer used by the skills below |
| Skills | `.claude/skills/` | `iw-implement`, `iw-commit-cycle`, `iw-pr-review`, `iw-docs-update`, `iw-ai-log`, `iw-scraper-conventions`, plus the OpenSpec skills |

All of it is committed, so the three of us run identical agents. The AI assistants are a development tool only: the product runs on local open-source models (Ollama).

## Lifecycle of one change

Intake (docs first, STATUS) → `iw-implement` (size, worktree) → `/openspec-propose`, human approves → `/openspec-apply-change` with `iw-commit-cycle` per task group → closing tasks (docs, log row, whole-branch review) → `/openspec-archive-change` as the last commit → human go-ahead → PR. Canonical stages and gates: `../.claude/SDLC.md`.

## Controls on generated code

- **Spec before code** for each capability (one OpenSpec change holds many tasks); `openspec validate --strict` before commit. A hook refuses service-code commits with no active change.
- **Tests first**, and a test must be able to fail: the test names the production change that turns it red.
- **Review per task group** by the shipped read-only `iw-reviewer` agent on a pinned `merge-base..HEAD` range, checking plan compliance against the OpenSpec change, then one whole-branch review before the PR. Every finding is verified against the code before it is acted on; false ones are rejected with evidence.
- **Deterministic guards**, not prompts: a tested hook denies force push, any push to `main`, amending pushed commits, and on commit a staged `.env`, `console.log` in JS/TS, and service code without an active change. Pushes and PR creation also require approval (`permissions.ask`).
- **Human gates**: spec approval, and a fresh go-ahead for every push and PR. ADRs are agent-written, committed as accepted, and take effect when the human approves and merges the PR.
- **Supply chain**: `pip-audit` / `npm audit` before merge (and via the manual CI workflow before milestones); secrets only in untracked `.env`.
- **Untrusted content**: scraped text is data. It is delimited, length-limited and never executed or used to pick a fetch target (prompt-injection and SSRF defence).
- **Optional**: a second reviewer from a different model family on high-risk diffs (contracts, credentials).

Known limits: review is a practice, not enforced by a hook; the hook reads only the staged diff (stage and commit in separate calls) and its escape flags are plain text, so it catches mistakes, not a determined agent; the second-family reviewer is not set up; this log is hand-appended (skill `iw-ai-log`); CI is manual-only for now.

## Log

| When | Who | What was done with AI | Outcome / lesson |
|---|---|---|---|
| Sat 11:15 | C | Read all 16 HackNation tasks and compared the top candidates (scope, criteria, constraints) | Team picked #InvestWatch |
| Sat 13:00 | C | Summarized the UKNF task, rules and annexes (18 risk-information rules, registry links, advisory definition) | Requirements in one place |
| Sat 13:40 | C | Drafted the integration plan (contracts, REST/WS API, milestones) and the analytics work plan | `.docs/integration-plan.md`, `.docs/analytics-plan.md` |
| Sat 14:10 | C | Applied team sync decisions; translated technical docs to English; started this log | English docs; OpenSpec adopted |
| Sat 14:05 | B | Generated a full service skeleton with Claude Code, then reviewed it against the team plan | The AI had filled open decisions (contracts, scraper design) with guesses from draft docs. Kept only the agreed repository structure; open decisions are left for ADRs |
| Sat ~13:50 | A | Had Claude Code adapt the Neopadel SDLC (keep/leave table first): OpenSpec, `iw-*` skills, a tested `git-guard` hook, SDLC and review docs. Then ran a fresh reviewer agent on the whole PR for team usability | PR #1. The independent review found real gaps the author missed (hook blind to `git add && git commit`, `git push origin HEAD` allowed on main, dependency on a personal plugin, contradictory sizing text, merge-conflict hot spots); all fixed, with the hook changes test-first |
| Sat pm | A | Ran the first real `/openspec-propose scraper-v1`; read the installed noble-tls, curl_cffi, httpx and queue-library APIs in a scratch venv to draft ADR options; ported `test-diff-check` (extended for pytest) and a stale-checkout SessionStart hook, both test-first | Draft ADRs 0101-0103 leave the decision blank for a human. A test caught a wrong fixture of mine (a rename target under `tests/` still counts as a test file). The stale-checkout hook was live-checked on a scratch clone two commits behind. Whole-branch review is the closing step of this PR |
| Sat ~15:20 | Damian | Had Claude Code draft ADRs 0301-0305: options from the plans and the task PDF, decisions picked by Damian in a multiple-choice quiz, then the agent wrote the rationale only from the reasons Damian selected; resolved the README merge conflict and moved the ADRs to the accepted-on-merge convention | PR #3. Adam's review caught what the agent missed: 0301 field-level freeze vs the file-level `git-guard` hook, 0304 contradicting the on-premise rule without evidence (fixed with the mentor exception and a local Gemma fallback), and accepted ADRs left contradicting `CLAUDE.md` and the plans (now updated in the same PR). Lesson: when an ADR contradicts a rule, update or check the enforcing file (hook, CLAUDE.md) in the same PR |
| Sat pm | A | Split `scraper-v1` into three parallel streams with saved session files, then applied `scraper-ingest` test-first against real PostgreSQL, Redis and MinIO containers, with a mutation check on every guard and an `iw-reviewer` pass per task group | Branch `scraper/scraper-ingest`. The agent had assumed the `documents` DDL, a `committed_at` column and a bucket-creating startup; C's real migration (`api/api-v1`) differed, so it was rebuilt against that after C replied (rule: read the peer's branch early, never a guessed schema). Reviewer caught blank text stored as a junk row, redaction missing 9 of 10 credential forms and orphan objects on non-Postgres errors and cancellation; mutation runs exposed three untested guards (`is_duplicate` scope, sweep order, dedup-check catch) and a test teardown that hung on a held row lock. CI would not run async or service tests: separate small PR. Human decides pushes and the PRs |
