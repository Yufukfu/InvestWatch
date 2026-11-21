# iw-watch: setup for people

`SKILL.md` tells the agent what to do. This file tells you how to switch it on.

## 1. What it needs

- Node >= 22.20 and `gh` logged in (`gh auth status`).
- For the headless mode: the `claude` CLI on `PATH`.

## 2. Discord notices (optional)

1. In Discord: the channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL. The URL is a secret: anyone who has it can post to the channel.
2. Put two variables in `~/.zshenv`, not `~/.zshrc`. zsh reads `~/.zshenv` in every shell, including the one the launchd job starts, so the terminal, `/loop` and the scheduled run all see them:

   ```sh
   export IWATCH_DISCORD_WEBHOOK="https://discord.com/api/webhooks/<id>/<token>"
   export IWATCH_NOTIFY_CMD="node $HOME/Projects/InvestWatch/.claude/skills/iw-watch/scripts/notify-discord.mjs"
   ```

   Then run `chmod 600 ~/.zshenv`. Never put the URL in the repository, in a `.env` that gets copied around, or in a skill file.
3. Test it: `node .claude/skills/iw-watch/scripts/notify-discord.mjs done "#0 test" https://github.com`.

The agent never sees these variables: the runner removes every `IWATCH_*` and `IW_*` variable from the environment of the session it starts.

## 3. Run it

| How | Command |
|---|---|
| In a Claude session | `/loop 2m /iw-watch --mine` |
| See what is waiting, no agent | `node .claude/skills/iw-watch/scripts/watch.mjs scan --mine --review-requested` |
| One headless pass, nothing published (the default) | `node .claude/skills/iw-watch/scripts/watch.mjs run --mine` |
| One headless pass that pushes and replies | `node .claude/skills/iw-watch/scripts/watch.mjs run --mine --publish` |
| Every 2 minutes in the background | `schedule/com.investwatch.iw-watch.plist` (macOS, logs to `~/Library/Logs/iw-watch.log`) or `schedule/crontab.example` |

A headless session runs in the Claude Code sandbox:
- no network;
- writes only inside its clone;
- no reads of `~/.ssh`, `~/.config/gh`, `~/.aws`, your shell profiles or `.env` files;
- no `GH_TOKEN` or `SSH_AUTH_SOCK` in its environment.

It cannot push or post. After the session the runner does both, with your own git and `gh` credentials, and only with `--publish`. Before publishing it checks that the tree is clean and that no commit touches `.claude/`, `CLAUDE.md`, `.github/` or `.mcp.json`. Every comment it posts starts with `iw-watch agent for @you, round N/3`. A sandboxed session can still read other files on your machine and quote them in its reply, so turn on `--publish` only on a machine without production credentials. See [ADR 0210](../../../.docs/decisions/0210-unattended-pr-watcher.md).

## 4. When it asks you something

The Discord message links to the agent's comment on the PR and lists the answers as comments, one copy box each:

```
/iw pager: w tym PR
```

Paste one as a comment on the PR. The next round reads it as your answer. You never run a shell command from a message.

## 5. If it is stuck

| Where | What |
|---|---|
| `~/.local/state/iw-watch/<owner>__<repo>/state.json` | What has been handled. Deleting it is safe: rounds are counted from GitHub. |
| `…/drafts/<item>/` | The agent's reply, its questions, summary.md (its last message) and `session.json` (cost, denied commands). |
| `../InvestWatch-worktrees/watch-pr-<n>` | The clone the agent worked in. It is kept when the run needs you; remove it to let the watcher retry. |
| `…/lock` | Held while a run is going; a lock older than 30 minutes is taken over. |
