## Why

PRs #47 and #48 both went into conflict with main and nobody noticed until the human looked. A watcher that misses a conflict leaves the PR unmergeable, so the hand-off between agents stops.

## What Changes

- `--mine` raises a `conflict` item when GitHub reports my PR as `CONFLICTING`, once per head sha.
- Headless: the runner merges `origin/<base>` in the clone. A clean merge is committed and pushed with no agent. Otherwise the agent resolves the conflicting files and runs the tests. The runner then refuses to go on if markers or unmerged paths remain, commits the merge, pushes it (never force) and posts the reply. A conflict in a protected path goes to the human.
- The push check compares protected paths against both the branch and the base, so the base's own `.claude/` changes that a merge brings in do not block it.
- In-session: SKILL.md handles `conflict` in the PR's worktree.

## Impact

`.claude/skills/iw-watch/` only.
