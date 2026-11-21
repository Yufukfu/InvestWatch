# 0210. An unattended PR watcher runs sandboxed agent sessions and publishes from the runner

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Kacper's decision after Adam's reviews of PR #48. It takes effect when the team approves and merges PR #48. Adam's and Damian's approvals of #48 are their sign-off; this ADR is not final without both, because it lets an agent act on every teammate's laptop without anyone at the keyboard

## Context

[ADR 0207](0207-agent-push-and-pr.md) lets an agent push its own branch and open a PR in an **interactive** session. A human is at the terminal, every push to something other than `origin` prompts, and the agent reads text the human chose to give it. PR #48 adds `iw-watch`, a runner (`.claude/skills/iw-watch/scripts/watch.mjs`) that every 2 minutes can start `claude -p` from launchd or cron. It runs on review text written by other people, with nobody watching. No ADR covered that, and the first PR body was wrong to say "all within ADR 0207".

Adam reviewed #48 three times on 2026-11-21 ([6008196884](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008196884), [6008229345](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008229345), [6008399494](https://github.com/Yufukfu/InvestWatch/pull/48#pullrequestreview-6008399494)). These are his blocking findings against the design at the time:

- A fix session cloned the PR branch, so that branch's `.claude/` hooks and settings ran. Project hooks run in `-p` even in an untrusted folder.
- Allowing the test runners (`node --test`, `npm test`, `pytest`) together with `Edit(./**)` is arbitrary code execution, outside every Claude rule and outside `git-guard`.
- `Read(./**)` does not bound Bash. He reproduced `git diff /abs/outside.txt /dev/null` printing a file outside the clone, and `gh pr view <url>` reading other repositories.
- `GH_TOKEN`, `SSH_AUTH_SOCK`, the user's MCP servers, plugins and allow rules reached the session.
- The push target was not validated: a fork PR from a branch named `main` would have pushed to `main`.
- An agent-written comment starting with `/iw` would be read as the human's answer on the next round.

He also pointed to the docs: Bash allow rules do not contain subprocesses, and the supported containment is the built-in sandbox passed via `--settings`.

## Options considered

1. **A laptop watcher whose `claude -p` sessions run in the Claude Code sandbox and publish nothing. The runner publishes after checks.**
   Evidence: a probe on Claude Code 2.1.330 in headless `-p`, run today with `--settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[]},"filesystem":{"denyRead":["~/.ssh","~/.config/gh","~/.aws"]}}}'`, `--setting-sources project` and `--strict-mcp-config`. A Node script started through the allowed Bash command got:
   - `EPERM` reading `~/.config/gh/hosts.yml` and listing `~/.ssh`;
   - `EPERM` writing a file in `~`;
   - `ENOTFOUND` on `fetch('https://api.github.com')`;
   - a successful write in the working directory.

   Environment variables still passed through, since `GH_TOKEN` was visible, so the runner has to filter the environment itself. A second probe with the exact argv and `runSession` of `lib/session.mjs`, with `GH_TOKEN=fake` in the parent, got these results (`.claude/skills/iw-watch/scripts/fixtures/README.md`):
   - `git diff /etc/hosts /dev/null` and `gh pr list` were denied;
   - inside `node --test`, `~/.config/gh` and `~/.zshenv` returned EPERM, the network returned ENOTFOUND and `GH_TOKEN` was unset;
   - `git add` and `git commit` worked. The PR workflow already works end to end with this runner: #39 was fixed and replied to by the watcher and then merged, and #40 got two rounds.
2. **[`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action) on GitHub runners.** This is the documented route for unattended PR and issue automation. It comes with a write-access gate, bot-actor rejection, per-PR concurrency and `--max-turns`, and it does not touch any laptop. Against it before the hand-in (Sun 2026-11-22 10:30):
   - it needs an Anthropic key or OAuth token in the repository's secrets, which an owner has to set up;
   - it needs a workflow per trigger, tested on real PRs;
   - each of the three teammates would need their own identity and budget.

   Its bot-actor protection also does not help with our setup, where agents post from human accounts. Deferred: a 30-minute spike after the hand-in.
3. **Only the in-session mode (`/loop 2m /iw-watch …`).** The human's own session runs under their normal permissions and the `git-guard` hook, and any prompt still reaches the person at the terminal. It is the safest option, but nothing happens while the laptop's session is closed, and the "agents hand work to each other" scenario then needs every teammate to keep a session open.

## Decision

Option 1. Option 3 stays the recommended default until the team has run Option 1 once with `--publish` on their own PR. Option 2 is the follow-up.

How each finding is held:

| Finding | Held by |
|---|---|
| Branch's own `.claude/` runs | The runner refuses a fix item whose diff from the merge-base with `origin/<base>` touches `.claude/`, any `CLAUDE.md`, `.github/` or `.mcp.json`. The hooks and settings that load are therefore the base branch's, which were already reviewed. It also checks that the clone's `HEAD` equals the head sha it scanned. A review item never checks out the PR head. |
| Tests are arbitrary code | Every session runs in the sandbox:<br>• no network (`allowedDomains: []`);<br>• writes only inside the clone;<br>• `denyRead` for `~/.ssh`, `~/.config/gh`, `~/.aws`, `~/.gnupg`, `~/.netrc`, `~/.npmrc`, `~/.docker`, `~/.kube`, `~/.zshenv`, `~/.zshrc`, the iw-watch state directory, and every `.env` in the main clone and its sibling worktrees;<br>• `failIfUnavailable` and `allowUnsandboxedCommands: false`.<br>The runner runs `npm ci --ignore-scripts` (exact) before the session, so the session needs no network. |
| Reads outside the clone, other repos | The sandbox's `denyRead` covers the secret paths above. A review session gets only:<br>• exact `git diff origin/<base>...refs/iw/pr-N` forms;<br>• `git show refs/iw/pr-N:<path>`;<br>• `git log` of that range.<br>Git arguments starting with `/`, `~` or `..` are denied, and a session gets no `gh` at all. |
| Credentials and user config | The runner builds the session's environment from an allow-list:<br>• `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_*`, `TERM`, `TMPDIR`, `TZ`;<br>• `CLAUDE_CONFIG_DIR`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`.<br>`GH_TOKEN`, `SSH_AUTH_SOCK` and the rest never reach it. `--setting-sources project` keeps out user-level allow rules, plugins and hooks, and `--strict-mcp-config` keeps out MCP servers. |
| Push target | The session cannot push (no network, no `git push` allow rule). The runner pushes with `git push origin HEAD:refs/heads/<headRef>`, never force, and only after these checks:<br>• the tree is clean;<br>• the new commits (`origin/<headRef>..HEAD`) touch no protected path;<br>• the PR is not cross-repository;<br>• `headRef` is neither the base nor the default branch. |
| Posting | The session writes .iw-watch/reply.md and optionally .iw-watch/issue.md. The runner posts at most one PR comment, whose first line reads `iw-watch agent for @<me>, round N/M` and which ends with the marker. It opens at most one issue, and only for an assignee who is a CODEOWNERS owner on the default branch and when no open issue already has the same title. |
| Agent comment taken as an answer | A comment carrying `<!-- iw-watch -->` is never an answer. Answers stay fenced as untrusted data. |
| Runaway and leaks | A timeout kills the whole process group, and `ENOBUFS` counts as a failure. Untrusted bodies are cut to 4000 characters before fencing. `run` is a dry run unless `--publish` is given. The plist logs to `~/Library/Logs/iw-watch.log` with mode 0600, not `/tmp`. |

A security pass by `iw-reviewer` on these fixes found seven more gaps, and each is closed:

| Gap | Closed by |
|---|---|
| A PR into an attacker-made base branch would load that branch's `.claude/` | Only PRs into the default branch get a session |
| A test can write `ANTHROPIC_API_KEY`, or any secret it can read, into reply.md | Before posting, the runner refuses a reply or issue that contains a known token shape or the literal value of a secret-looking variable it holds |
| Secrets outside the first `denyRead` list | `~/.claude.json`, all of `~/.config`, `~/.azure` and `~/.gcloud` are added. The same paths are also `Read` deny rules, because the sandbox bounds Bash, not the Read tool. Branches that add a symlink are refused |
| Sandboxed code can write `.git/config` or hooks, which the runner's own git would then run | Config, hooks and attributes are snapshotted before the session and compared after it. On a change, no git runs; otherwise git runs with `core.hooksPath=/dev/null` and `core.fsmonitor=false` |
| `.Claude/` on a case-insensitive disk; a branch `.npmrc` steering `npm ci` | The protected-path check ignores case and covers `.npmrc` and `.yarnrc` |
| Background test processes outliving the session | The process group is killed after every session, not only on a timeout |

**The boundary that is left:**
- The runner pushes and comments with the user's own git and `gh` credentials, outside the sandbox, so a published reply is posted as that person.
- A sandboxed session can still read files that are not in `denyRead` and copy them into reply.md, which the runner then posts on the PR.
- Agents post from human accounts, so the round cap (default 3) and the event-id dedupe are the only loop protection. GitHub's bot-actor checks do not apply.

**Rationale:**
- The probe shows that the sandbox, not the allow-list, contains code the session runs.
- Moving every publish into the runner means the only outward actions are a fixed push and comment that deterministic code checks before acting.
- Option 2 is the better end state, but it costs a setup the team cannot finish and test before the hand-in.

## Consequences

- An unattended watcher may post on a teammate's PR as you. Turn on `--publish` only on a machine without production credentials outside the `denyRead` list.
- The sandbox must be available (macOS Seatbelt, Linux bubblewrap). With `failIfUnavailable` the session fails rather than running unsandboxed.
- A PR whose branch changes `.claude/`, `CLAUDE.md`, `.github/` or `.mcp.json` is never fixed headless. The human handles it in their own session.
- Test suites that need the network or write outside the repository fail in the sandbox. The agent reports that in its reply instead of working around it.
- Follow-ups after the hand-in:
  - the `claude-code-action` spike (Option 2);
  - a dedicated low-scope `gh` token for the runner;
  - checking the collaborator permission instead of `author_association`.
