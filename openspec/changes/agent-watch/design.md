# Design

## Context

See proposal.md for motivation. Facts that shape the approach, checked in the repository on 2026-11-21:

- PR #27 ([ADR 0207](../../../.docs/decisions/0207-agent-push-and-pr.md)) lets an agent push its own branch to `origin` and open a PR without a prompt (`permissions.allow`: `git push origin`, `git push -u origin`, `gh pr create`), keeps `gh pr merge`, `gh pr ready` and `gh pr review` under `ask`, and hardens `.claude/hooks/git-guard.js` (push to `origin` and the current branch only, push options as an allow-list, no merge or approve through `gh api`, none of it escapable). The human approves and merges every PR. This change builds on that and changes none of it.
- The hook is a text guard against mistakes, not a security boundary (its header says so). `main` has no branch protection, so "a human approves" is a team convention.
- The three teammates have different machines, GitHub logins (`kacpermalczyk`, `hen68` for Adam, `Yufukfu` for Damian, from `gh pr list`) and Claude accounts. There is no public endpoint, so GitHub webhooks are out; polling with `gh` is what works on a laptop. `gh` is 2.39 here; only stable `--json` fields are used (and `gh pr edit` is broken on it, so the runner never calls it).
- CI runs `node --test` on `.claude/**` scripts, so the runner is Node ESM (`.mjs`, Node >= 22.20, no new dependency).
- The `claude` CLI is not on `PATH` in the authoring session, so its flags were not verified there; they come from the Claude Code docs and are pinned in task 4.2.

## Goals / Non-Goals

**Goals:** an item is detected within about two minutes, handled once, bounded in cost and rounds, and acted on under exactly the rules a person's session has; small enough to finish and demo before 10:30.

**Non-Goals:** webhooks, a chat bot, merging or approving, learning from past reviews, multi-repo support, changing `settings.json`, the hook or `CLAUDE.md`.

## Decisions

### D1. The runner decides what to do, the model decides how

`scripts/watch.mjs` is deterministic: it polls, filters, dedupes, enforces caps and builds the prompt. The model reads, edits, commits, and (headless) pushes its branch and comments, all through the allow-list below. Alternative: let a `/loop` prompt do everything. Rejected: cost on every empty poll, no testable dedupe, and no place to hold limits.

CLI: `watch.mjs scan|ack|run [--mine] [--review-requested] [--author L] [--domain D] [--max-rounds N] [--json] [--dry-run]`.

### D2. A headless session gets the same permissions as an interactive one, and no more

`claude -p` runs with `--permission-mode dontAsk` and an explicit allow-list that mirrors ADR 0207: read and edit tools, local `git`, `git push origin`, `gh pr create`, `gh pr comment`, `gh issue create`. Anything else (`gh pr review`, `gh pr merge`, `gh pr ready`, `gh api`, network tools) is denied because nothing is there to answer a prompt, and the project's `git-guard` hook loads from the worktree's `.claude/settings.json` and still runs. Alternatives:

- A runner that performs the push and the `gh` writes itself ("model proposes, runner disposes", the first version of this design): the runner would push outside the hook, so every guard would have to be written twice. Dropped once ADR 0207 made the model's own push the sanctioned path and the hook the guard.
- Bypass permissions in a container: no container on laptops, and `bypassPermissions` is documented for isolated VMs only. Rejected.

Reviews of other people's PRs go out as `gh pr comment`, never `gh pr review`, so the agent cannot approve even by mistake and the human's approval stays the gate.

### D3. Round cap through a marker in the text, backed by state

Every comment and issue body the agent writes ends with `<!-- iw-watch -->` (the prompt says so). Rounds on a PR are the larger of the marked comments by the current user, counted from GitHub, and the sessions the runner recorded for that PR. A wiped state file or a second laptop cannot reset the count, and an agent that forgets the marker is still counted by the state. Two watchers (mine and Damian's) that answer each other stop at the cap on both sides.

### D4. Untrusted text is data, and the allow-list is the real defence

The prompt puts all third-party text inside a fence ("data, not instructions"), but a fence only lowers the odds. The hard limit is the allow-list: no network tool, no `gh api`, no review, merge or ready, `--max-turns` capped, text never interpolated into argv, and the hook's push rules on top. The worst a prompt-injected session can do is write wrong code to its own branch or post a wrong comment, and a human reviews both before merge.

### D5. In-session mode needs nothing new

`/loop 2m /iw-watch --mine` runs `scan --json`; the session handles the item under its own permissions, as for any task. This is the demo path.

### D6. One worktree per handled item

`run` creates `../InvestWatch-worktrees/watch-pr-<n>` from the PR head (fetched with `refs/pull/<n>/head` for reviews, the real branch for the user's own PRs) so the main clone and other sessions are not touched, and removes it afterwards unless the item needs the human.

### D7. State outside the repo

`${XDG_STATE_HOME:-~/.local/state}/iw-watch/<owner>__<repo>/` holds `state.json`, `drafts/` and a lock directory (atomic `mkdir`). Nothing in it is committed, and it holds no tokens: `gh` keeps its own auth.

### D8. CODEOWNERS is the routing table, read from the default branch

Owners follow [`.docs/STATUS.md`](../../../.docs/STATUS.md): `scraper/` Adam, `web/` and `infra/` Kacper, `analytics/`, `api/`, `contracts/` Damian, `.docs/` and `openspec/` shared, so left to everyone. Reading the default-branch copy stops a PR from rerouting its own review. The parser implements the subset in use (directory and glob patterns, last match wins) and fails closed on syntax it does not know.

## Risks / Trade-offs

- **Prompt injection through PR text** → allow-list, data fence, the hook, round cap; residual risk is a bad commit on the agent's own branch or a wrong comment, both seen by a human before merge.
- **Agent ping-pong between two watchers** → marker plus state cap (D3), one `needs-human` notice, silent afterwards.
- **Depends on PR #27** → until it merges the headless push is denied; the item then stays a draft with a `needs-human` notice, and `--dry-run` covers the same path on purpose.
- **Escape flags** (`IW_*`) are plain text and a headless agent could write one → the hook's push and `gh` checks take no escape; a commit made with `IW_SKIP_SPEC=1` is still possible, so the runner's prompt forbids `IW_*` and the PR body must list any escape used (ADR 0207 criterion).
- **Cost** → polling is plain `gh` (no model) and a session starts only on a new item, with `--max-turns` and a per-run item limit.
- **Unverified `claude` flags** → built in one function and pinned by a test against `claude --help` output saved from the first machine that has it (task 4.2); a flag change is a one-line fix.
- **`gh` 2.39 is old** → only `pr list/view --json`, `api` GET for reviews and comments (done by the runner, not the agent), `issue create`, `pr create`, `pr comment`.
- **Time** → v1 is `--mine` and `--review-requested`; `--author`, `--domain` and owner-routed issues land in later task groups and can be cut without breaking the rest.
