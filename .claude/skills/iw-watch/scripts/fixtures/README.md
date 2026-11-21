# Fixtures

Saved `gh` output from this repository on 2026-11-21, trimmed (bodies cut to 200 characters, file lists shortened):

- `pr-11.json`, `reviews-11.json`, `review-comments-11.json`: `gh pr view 11 --json ...` and `gh api repos/Yufukfu/InvestWatch/pulls/11/{reviews,comments}` (Adam's review on Kacper's PR).
- `pr-28.json`: `gh pr view 28 --json ...` (Damian's PR), used as a review request.
- `pr-list-mine.json`, `reviews-27.json`: PR 27 and its reviews.
- `pr-comments.json`: the shape of `gh api repos/.../issues/27/comments`; the `<!-- iw-watch -->` markers and the last two entries are added for the round-count tests.
- `checks-failed.json`: written by hand in the shape of `statusCheckRollup` (CheckRun and StatusContext), since no PR here had a failing check when the fixtures were saved.
- `claude-help.txt`: `claude --help` of Claude Code 2.1.330 (the runtime on the authoring machine, 2026-11-21). `session.test.mjs` pins every flag the runner passes against it.
- `claude-stream-denied.jsonl`: a real `claude -p --permission-mode dontAsk --output-format stream-json` run (Haiku, $0.12) asked to `git push --force origin main` with only `Bash(git status:*)` allowed: the `init`, `permission_denied` and `result` lines, trimmed. The denial is in `result.permission_denials[].tool_input.command`.

## Permission probes (not fixtures, the evidence behind lib/session.mjs)

Three real `claude -p --permission-mode dontAsk` runs on 2.1.330 (Haiku, about $0.55 in all), in throwaway directories with decoy files only, 2026-11-21:

- `Read(./**)` allowed `./a.txt` and denied a decoy outside the directory, for Read and for Grep.
- `--disallowedTools` beat an allow rule (`echo proj`, allowed by project settings and by the read-only default, was denied).
- `Write(./.iw-watch/**)` did not allow the write; `Edit(./.iw-watch/**)` did, and `./c.txt` stayed denied.
- `Bash(touch 11 *)` allowed `touch 11 y` and denied `touch 110 x`; `Bash(touch * --repo *)` as a deny blocked `touch 11 --repo z`; `GH_REPO=x touch 11 q` and `touch 11 w && touch evil` were denied.
- A project `allow` rule was ignored: stderr said "Ignoring 1 permissions.allow entry from .claude/settings.json: this workspace has not been trusted".
- A project `PreToolUse` hook in the same untrusted directory ran and blocked the command, and the block was listed in `permission_denials`; a hook passed with `--settings` ran too.
