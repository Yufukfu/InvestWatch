# 0207. Agents push their branch and open the PR; humans approve and merge

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the team (decision taken in the team chat), effective when the human merges the PR

## Context

The root [`CLAUDE.md`](../../CLAUDE.md) said "No push, PR or merge without a fresh explicit go-ahead from the human", `.claude/SDLC.md` stage 7 made push and PR a human step, and `.claude/settings.json` put `git push` and `gh pr create` in `permissions.ask`, so every push prompted. Every change already passes the same gates before a PR exists: failing test first and a mutation check per task group, `iw-reviewer` per group and once over the branch, `docs-check`, the archive as the last commit, and the PR-ready criteria in [`.claude/CODE_REVIEW.md`](../../.claude/CODE_REVIEW.md). The git hook (`.claude/hooks/git-guard.js`, tested) already denies force push, any push to `main`, `--all`/`--mirror` and amending a pushed commit.

## Options considered

1. **Keep the human push and PR step.** Safest, but each PR waits for a person at the terminal, and the push itself adds no check the gates and the review do not already give.
2. **Agent pushes its branch and opens the PR; human approves and merges.** The human decision that matters (is this good enough for `main`) stays with the human at review and merge; a push of a feature branch is reversible and published nothing to `main`.
3. **Agent also merges.** Removes the last human gate; rejected, since the ADR rule "takes effect when the human approves and merges" and the review bar depend on it.

## Decision

Option 2. An agent pushes its own feature branch and opens the PR once the PR-ready criteria hold. The human approves and merges every PR. The agent never merges, approves or marks a PR ready for someone else. The hook keeps denying `main`, `--force` and amending a pushed commit, so "nothing straight to `main`" stays enforced by code. `git push` and `gh pr create` move from `permissions.ask` to `permissions.allow`; `gh pr merge` and `gh pr ready` stay in `ask`.

Rationale: the existing gates run before the push in both options, the hook blocks the dangerous pushes in code, and merge remains the human gate. The team accepted it.

## Consequences

- A PR can appear without anyone typing a go-ahead, so the PR body must list every behaviour change and every `IW_*` escape used (already a review criterion in `.claude/CODE_REVIEW.md`).
- A pushed commit is public: an agent that pushes too early cannot amend it, only add fix commits. The criteria in `.claude/CODE_REVIEW.md` apply before the first push.
- The hook is a guard against mistakes, not a security boundary (its own header says so); reviewers and the human merge are the real control.
- Supersedes the "fresh go-ahead" wording in `CLAUDE.md`, `.claude/SDLC.md`, `.claude/CODE_REVIEW.md`, `iw-pr-review` and `openspec/config.yaml`.
