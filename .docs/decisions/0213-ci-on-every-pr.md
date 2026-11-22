# 0213. CI runs on every pull request, as an advisory check

- Status: accepted
- Date: 2026-11-22
- Deciders: Kacper; agent-written; effective when the human merges the PR. Team-wide: Adam's and Damian's PRs get the checks too.

## Context

`.github/workflows/ci.yml` runs tests, lint, type checks, `pip-audit` and `npm audit` for every service, plus `docs-check`, the AI-log check and `openspec validate`. It was `workflow_dispatch` only, "to keep the 24h hackathon fast". [ADR 0209](0209-supply-chain-scanning.md) kept it that way ("CI stays `workflow_dispatch` during the hackathon") and [`.claude/SDLC.md`](../../.claude/SDLC.md) stage 8 says the same.

Evidence, read with `gh` on 2026-11-22:
- `ci.yml` has run 6 times in total. The last run on `main` was 2026-11-21 19:49 UTC (success, 165 s). Since then, 55 PRs were merged without any `ci.yml` run, so a broken test or lint error on `main` is seen only when someone starts it by hand.
- Job times in that run: Python 3.12 162 s, Python 3.13 96 s, Node 51 s, contracts 40 s, specs and hooks 14 s, debug output 6 s. The jobs run in parallel, so a PR waits about 3 minutes.
- Billing rounds each job up to a whole minute, so one run costs about 9 Actions minutes. The repository is private on an owner's GitHub Free account, which includes 2,000 minutes a month for private repositories. That figure is GitHub's published Free-plan quota, not read from the account's billing page, which needs owner access.
- Required status checks are not available. `main` has no branch protection (`protected: false`), and the rulesets API answers 403: "Upgrade to GitHub Pro or make this repository public".

## Options considered

1. **Keep `ci.yml` manual.** Costs nothing, but the 55 merges above show that nobody runs it. A PR shows green security checks ([ADR 0209](0209-supply-chain-scanning.md), `security.yml`) while its tests may be red.
2. **Run `ci.yml` on every PR to `main` as an advisory check.** Every PR shows each job's result in about 3 minutes. Red does not block the merge: the reviewer checks it, as `security.yml` is checked.
3. **Run it on every PR and make it a required check.** A real gate, but it needs a paid plan or a public repository (403 above), which the team has not decided.

## Decision

Option 2. `ci.yml` gets a `pull_request` trigger for `main`, next to `workflow_dispatch`, plus `concurrency` with `cancel-in-progress` per ref, so a new push cancels the older run and does not spend its minutes. It is not a required check: a PR with a red `ci` job is not merged until the job is green, or until the PR body explains why the failure is unrelated. The reviewer checks this, as `.claude/CODE_REVIEW.md` already asks for green deterministic checks.

This replaces ADR 0209's line "CI stays `workflow_dispatch` during the hackathon", and SDLC stage 8.

## Consequences

- Every PR to `main` runs `ci` and `security`. They start together, so the wait is the slower of the two, about 3 minutes.
- About 9 Actions minutes per push for `ci`, plus about 7 for `security`: roughly 125 pushes a month within the Free quota. If the quota runs out, jobs stop starting until the next month; nothing is charged while the account's spending limit stays 0.
- A PR from a fork runs with a read-only token and no secrets. `ci.yml` uses no secrets; its test credentials are fixed test-only values.
- Making the checks required stays open: it needs a paid plan or a public repository. That is a team decision.
