# Proposal

## Why

Three people each run their own Claude agent and hand work to each other through GitHub PRs and issues, but nothing wakes an agent when a review lands, a review is requested or a backend answer is wrong. Today every hand-off waits for a human to notice, then open a session. The hackathon jury scores how we use agents to produce code ([`.docs/ai-workflow.md`](../../../.docs/ai-workflow.md)); an agent that watches the repo and acts on review activity is the clearest demonstration, and it saves real time before the Sun 2026-11-22 10:30 hand-in.

## What Changes

- New skill `iw-watch` (`.claude/skills/iw-watch/`) plus a deterministic Node runner (`scripts/watch.mjs`) that polls GitHub through `gh` for work addressed to the current user: `--mine` (new reviews, comments and failing checks on my PRs) and `--review-requested` (PRs waiting for my review).
- Overlay filters: `--author <login>` and `--domain <dir>` (a PR that touches a directory I own). Owners come from a new `.github/CODEOWNERS` (`scraper/` Adam, `web/` and `infra/` Kacper, `analytics/`, `api/` and `contracts/` Damian), the same split as [`.docs/STATUS.md`](../../../.docs/STATUS.md).
- A seen-state file outside the repo so an item is handled once; a per-PR round cap (default 3) stops agent-to-agent ping-pong; PR, review and issue text is treated as untrusted data.
- Two ways to run: in a session (`/loop 2m /iw-watch --mine`) or headless (`claude -p` started by the runner from launchd or cron, documented example). A headless session acts under the same rules as an interactive one ([ADR 0207](../../../.docs/decisions/0207-agent-push-and-pr.md), PR #27): it may push its own branch to `origin` and open a PR, never merge, approve or mark ready, and the `git-guard` hook stays active. It posts reviews as comments only.
- Report-to-owner: when the agent finds a defect in code owned by someone else (for example the backend returns a wrong shape), it opens a GitHub issue assigned to the CODEOWNERS owner instead of editing their code.
- `--dry-run` keeps every outward result as a draft in the state directory for the human to publish.

Builds on PR #27 (ADR 0207, merged 2026-11-21): the agent may push its own branch and open a PR, and the hardened hook guards it. The headless runner is narrower still (one branch, one PR per session), since an untrusted clone ignores project allow rules and the runner passes its own.

- Notifications: a JSON line per notice and an optional command (`IWATCH_NOTIFY_CMD`); `notify-discord.mjs` is a ready one that posts to a Discord channel webhook, so teammates see "done" and "needs you" in the team channel.

Out of scope: a Discord bot that takes commands (the channel only receives notices), merging, approving, webhooks and a public endpoint, any change to `settings.json`, the hook, `CLAUDE.md` or contracts, REST routes or events. Owner: Kacper (tooling, `chore/*`); `CODEOWNERS` touches all three owners' areas, so it needs the team's OK in review.

## Capabilities

### New Capabilities

- `agent-watch`: polling, filtering by user, author and domain, CODEOWNERS routing and owner-routed issues, seen-state, round cap, untrusted-text handling, headless restrictions, dry-run drafts, in-session and headless modes.

### Modified Capabilities

<!-- none: no existing spec changes -->

## Impact

- New files: `.claude/skills/iw-watch/` (skill, runner, tests), `.github/CODEOWNERS`.
- Edited files: `.claude/SDLC.md` and `.docs/ai-workflow.md` (skill lists), `.docs/INDEX.md`, `.docs/status/dashboard.md`, `.github/workflows/ci.yml` (add the new test glob), the AI log row. No ADR: the push and PR rule is ADR 0207; the one choice made here (round cap by marker) is recorded in `design.md`.
- Touches no contract, REST route or event. No new dependency: Node >= 22.20 and `gh` are already required; the headless mode also needs the `claude` CLI on `PATH`.
- Security-relevant: it reads text written by other people and can act on a repository. Review runs with `focus: security`.
