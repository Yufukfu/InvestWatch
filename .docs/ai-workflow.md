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
| Sat 15:00 | B | Claude Code set up the web foundation (OpenSpec change `web-setup`): Vite/React app, RTK Query client generated from the OpenAPI contract, MSW over the contract mocks, hardened nginx image, Postgres and a Caddy HTTPS gateway in per-module compose files | Contract-first client: hand-written requests are not needed. Docker Hub rate-limited anonymous pulls, so images come from the official AWS ECR mirror |
| Sat 15:30 | B | Damian reviewed PR #6 with Claude Code; Claude Code verified each point against the code and fixed all nine | The second review caught what the first agent review missed: a test that mutated a committed file under parallel runs, a dev setting silently ignored, gateway gaps. Auto mode also blocked an `IW_SKIP_SPEC=1` commit, so the fixes got their own OpenSpec change instead |
| Sat ~15:20 | Damian | Had Claude Code draft ADRs 0301-0305: options from the plans and the task PDF, decisions picked by Damian in a multiple-choice quiz, then the agent wrote the rationale only from the reasons Damian selected; resolved the README merge conflict and moved the ADRs to the accepted-on-merge convention | PR #3. Adam's review caught what the agent missed: 0301 field-level freeze vs the file-level `git-guard` hook, 0304 contradicting the on-premise rule without evidence (fixed with the mentor exception and a local Gemma fallback), and accepted ADRs left contradicting `CLAUDE.md` and the plans (now updated in the same PR). Lesson: when an ADR contradicts a rule, update or check the enforcing file (hook, CLAUDE.md) in the same PR |
| Sat 17:55 | B | B asked Claude Code to add lint and typecheck to CI (a gap hen68 found: the layering guard had only been checked through `npm test`); done as small change `ci-lint-typecheck`, verified by running the chain locally with a deliberate `console.log` | Not verified on GitHub Actions until the workflow runs; CI is advisory (SDLC stage 8) |
| Sat 17:40 | B | Second round on PR #12 with Claude Code: hen68 approved and listed what the lint guard still misses; the agent added the `store/` folder pattern test-first (small change `layering-store-folder`) and wrote the remaining gaps into the rule instead of claiming full coverage | The earlier PR body had a wrong test count (35 new of 70); the reviewer recomputed it. Numbers in PR bodies now come from a run, not from memory |
| Sat 17:25 | B | Fixed hen68's review of PR #12 through a second small OpenSpec change (`layering-review-fixes`): reproduced the holes first (nested component folders, `.tsx` extension, package subpaths), widened the lint patterns, added a test that lints the real components, then fixed the label fallback and the data-layer-imports-component direction and closed the test gaps | The first change claimed "the layering is a CI check" while CI only runs `npm test`, and the agent had tested the config on synthetic files only; the reviewer found both by trying a real violation. Mutation checks again found missing cases (4 of 14 pattern mutants survived until bare-form cases were added) |
| Sat 17:05 | B | Had Claude Code apply ADR 0204 through OpenSpec change `feature-layering`: lint guard first (oxlint `no-restricted-imports` on components, tested by running the real config), then health, summary and findings split into data hook, props-only component and page, each test-first with a mutation check | Two process slips caught by the checks, not by the agent: it committed the lint test without running `tsc` (Node types missing in the browser tsconfig), and its first mutation run on findings was void because the baseline was already red from a test bug. The mutation step now starts from a green baseline; one health mutant survived and led to an extra test for a response without `status` |
| Sat 16:17 | B | Asked Claude Code what the frontend architecture rules are; it found none beyond the props rule and that the existing components import generated hooks directly. Wrote ADR 0204 (feature data hooks as the boundary to the generated client, view models, presentational components) and extended the rule, comparing hooks, container components and the status quo against the code | The swap test decided it: `generated.ts` is RTK-specific, so with the status quo replacing RTK Query touches every component. Container components add a tree level without more isolation. The ADR records that the existing components are not moved yet: that is code, so it waits for an OpenSpec change Review of PR 11 then found the draft overstated what the code shows (store and test setup also import `generated.ts`, `HealthBadge` is 20 lines, container components compared too thinly) and that the layering had no lint enforcement; the ADR was rewritten with those facts |
| Sat 15:58 | B | Turned the task's chart criteria (Chart.js or Recharts) into ADR 0203 with Claude Code: compared the two libraries on npm metadata (licence, React 19 peer range, wrapper needed or not) and wrote the decision and its consequences; then a path-scoped rule `.claude/rules/web-dashboard.md` for the dashboard (props architecture, risk presentation, Polish texts, calibration) from the task criteria | Recharts chosen for its declarative, prop-driven components. The rule drops the criteria that belong to the analytics rules (R1-R18 identity, forecasts, KNF references) and keeps the ones that govern how risk is shown. Library not installed yet: the install waits for an OpenSpec change |
