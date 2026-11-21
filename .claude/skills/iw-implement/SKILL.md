---
name: iw-implement
description: Use at the start of any feature, fix or refactor that will become its own PR, before writing code. Gives an isolated git worktree on a fresh branch off latest main, bound to an OpenSpec change. Not for reviewing someone else's PR.
---

# iw-implement

One task = one OpenSpec change = one worktree = one branch = one PR. Parallel sessions never share a checkout.

## Steps

1. **Size it.** One-file fix or docs typo: skip the spec, put the plan in the PR body, and use `IW_SKIP_SPEC=1` on the commit. Anything that touches a contract (`contracts/`), a service boundary or more than one file: OpenSpec change (next step). Unclear scope: `/openspec-explore` first.
2. **Branch name** follows the module prefix from `doc/plan-integracji.md` §7: `scraper/<slug>`, `analytics/<slug>`, `dashboard/<slug>`, or `chore/<slug>` for tooling and docs. The slug equals the OpenSpec change name.
3. **Worktree**, from the main clone (never `cd` back into it afterwards):
   ```bash
   git fetch origin main
   git worktree add -b <prefix>/<slug> ../InvestWatch-worktrees/<slug> origin/main
   ```
4. **Spec**: in the worktree run `/openspec-propose <slug>`. Read `doc/STATUS.md` and the owning spec under `openspec/specs/` first. Contracts are frozen per `doc/plan-integracji.md` (v1): a change that alters one needs the whole team's OK and a version bump, so say so in the proposal.
5. **Stop for review of the spec** by the human before implementing. Then `/openspec-apply-change`, one commit per task group, each through `iw-commit-cycle`.

## Don't

- Don't start in the main clone or on `main`.
- Don't let two worktrees hold changes touching the same spec file; check `openspec list` first and coordinate.
- Don't remove the worktree before the PR is merged and `/openspec-archive-change` has run.
