# Proposal

## Why

Adam reviewed PR #48 on 2026-11-21 and requested changes three times ([6008196884](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008196884), [6008229345](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008229345), [6008399494](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008399494)). His blocking findings:

- A fix session runs the PR branch's `.claude/` hooks.
- The test runners in the allow-list are arbitrary code execution.
- Reads leak outside the clone (`git diff /abs`, `gh pr view <url>`).
- Credentials and user config reach the session.
- The push target is not validated.
- No ADR covers unattended operation.
- An agent-written `/iw` comment is read as the human's answer.

The claim "a session can push only its own branch and comment only on its PR" has to be enforced, not promised.

## What Changes

- **The runner publishes, not the session.**
  - A headless session has no `gh` and no `git push`. It writes .iw-watch/reply.md and, if needed, .iw-watch/issue.md.
  - After checks, the runner pushes `HEAD:refs/heads/<headRef>` (never force).
  - It posts one comment whose first line reads `iw-watch agent for @<me>, round N/M` and which ends with the marker.
  - It opens at most one issue, assigned to a CODEOWNERS owner, after a check for duplicates.
- **Sandbox.** Every session runs in the Claude Code sandbox, set through `--settings`: no network, writes only inside the clone, `denyRead` for credential paths, the state directory and `.env` files, and `failIfUnavailable`. It also gets an environment allow-list, `--setting-sources project` and `--strict-mcp-config`.
- **Fix-branch checks.** A fix item is refused when:
  - its diff from the merge-base touches `.claude/`, `CLAUDE.md`, `.github/` or `.mcp.json`;
  - the clone's `HEAD` differs from the scanned sha;
  - the PR comes from a fork;
  - the head branch is the base or default branch.

  Dependencies are installed by the runner (`npm ci --ignore-scripts`) before the session.
- **Review sessions** get exact `git diff`/`git show`/`git log` forms on `refs/iw/pr-N` only. Git arguments starting with `/`, `~` or `..` are denied.
- **`/iw` answers.** A comment carrying `<!-- iw-watch -->` is never an answer, and answers stay fenced as data.
- **Robustness.**
  - A timeout kills the process group, and `ENOBUFS` is a failure.
  - Untrusted bodies are cut to 4000 characters.
  - `run` is a dry run unless `--publish` is given.
  - The plist logs to `~/Library/Logs/iw-watch.log`.
- **Docs.** [ADR 0210](../../../.docs/decisions/0210-unattended-pr-watcher.md) records the unattended mode and its remaining boundary. README and SKILL.md are updated.

Out of scope: the `iw-issue` skill and the `address-issue` item kind (Adam's second review), cutting `--domain` and Discord, and the `claude-code-action` spike. These are follow-ups after the hand-in.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `agent-watch`: headless restrictions, the per-session allow-list, publishing, dry run by default, untrusted text and `/iw` answers, and owner-routed issues.
