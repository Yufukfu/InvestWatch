---
name: iw-implement
description: Use at the start of any feature, fix or refactor that will become its own PR, before writing code. Sizes the work, creates the isolated worktree and branch, then hands over to the OpenSpec skills (explore, propose, apply). Not for reviewing someone else's PR; not a replacement for /openspec-propose.
---

# iw-implement

**One OpenSpec change = one worktree = one branch = one PR.** A change covers a capability (for example `scraper-v1`), not a single task; its tasks live in `tasks.md`. Implementation always runs through the OpenSpec skills; this skill only prepares the ground.

## Steps

1. **Size it.**
   - One-file fix, parser or source added to a capability that already has an active change, bug fix, docs typo: no new change. Add tasks to the existing change, or if none is active put `IW_SKIP_SPEC=1` on the commit and say so in the PR body.
   - A new capability, anything touching a contract (`contracts/`) or a service boundary, anything security-relevant: an OpenSpec change (step 4).
   - Foggy scope: run `/openspec-explore` first.
2. **Branch name**: `<prefix>/<slug>` where the prefix is the module: `scraper/`, `analytics/`, `api/`, `dashboard/`, `contracts/`, or `chore/` for tooling and docs. The slug equals the OpenSpec change name. (`doc/integration-plan.md` §7 lists only the first three; `api/` and `contracts/` are C's.)
3. **Worktree**, from your main clone (never `cd` back into the main clone afterwards):
   ```bash
   git fetch origin main
   git worktree add -b <prefix>/<slug> ../InvestWatch-worktrees/<slug> origin/main
   ```
   A fresh worktree has no untracked files: copy your `.env` from the main clone (never commit it) and install the module's dependencies. For parallel stacks set `COMPOSE_PROJECT_NAME=iw-<slug>` and avoid port clashes.
4. **Spec, using the OpenSpec skills**: read `doc/STATUS.md` and the owning spec under `openspec/specs/`, then run `/openspec-propose <slug>`. A change that alters a frozen contract (`doc/integration-plan.md`, v1) says so in the proposal and needs the whole team's OK and a version bump.
5. **Stop for the human to approve the spec.** Then implement with `/openspec-apply-change` only; do not code outside the apply flow. Per task group `iw-commit-cycle` applies (the config guidance in `openspec/config.yaml` says so), and the closing tasks generated into `tasks.md` finish the change.

## Don't

- Don't start in the main clone or on `main`.
- Don't let two worktrees hold changes touching the same spec file; check `openspec list` and coordinate.
- Don't remove the worktree before the PR is merged.
