# Tasks

Reviews: Adam on PR #48 (6008196884, 6008229345, 6008399494). Tests: `node --test ".claude/skills/iw-watch/scripts/*.test.mjs"`.

## 1. Runner publishes

- [x] 1.1 Remove `gh` and `git push` from every session allow-list. After the session the runner checks the clean tree and that the new commits touch no protected path. It then pushes `HEAD:refs/heads/<headRef>`, never force, and posts reply.md with the visible agent line and the marker. It opens at most one issue from issue.md, with a CODEOWNERS assignee and a duplicate check.

## 2. Sandbox

- [x] 2.1 Pass `--settings` with the sandbox:
  - enabled, `failIfUnavailable`, `allowUnsandboxedCommands: false`;
  - no network;
  - `denyRead` for the credential paths, the state directory and every `.env` in the main clone and its sibling worktrees.

## 3. Environment and user config

- [x] 3.1 Build the session environment from an allow-list, then add `--setting-sources project` and `--strict-mcp-config`.

## 4. Fix-branch checks

- [x] 4.1 Refuse a fix item when:
  - its diff from the merge-base touches `.claude/`, `CLAUDE.md`, `.github/` or `.mcp.json`;
  - `HEAD` does not equal the scanned sha;
  - it is a cross-repository PR;
  - the head branch is the base or default branch.
- [x] 4.2 The runner installs dependencies (`npm ci --ignore-scripts`, exact) before the session.

## 5. Review session reads

- [x] 5.1 Give a review session only the exact `git diff`/`git show`/`git log` forms on `refs/iw/pr-N`. Deny git arguments starting with `/`, `~` or `..`, and give it no `gh`.

## 6. `/iw` answers

- [x] 6.1 Make sure a marked comment is never an answer, and fence answers as data. Add a test: a marked comment starting with `/iw` produces no answer.

## 7. Robustness

- [x] 7.1 A timeout kills the process group, and `ENOBUFS` is a failure.
- [x] 7.2 Cut untrusted bodies to 4000 characters before fencing.
- [x] 7.3 Make `run` a dry run unless `--publish` is given.
- [x] 7.4 Point the plist log at `~/Library/Logs/iw-watch.log`.

## 8. Closing

- [x] 8.1 ADR 0210, README, SKILL.md and `docs-check`.
- [ ] 8.2 Run `iw-pr-review` with `focus: security`, then `/openspec-archive-change` as the last commit.
