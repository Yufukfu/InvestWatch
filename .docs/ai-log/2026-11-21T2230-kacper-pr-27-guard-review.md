---
when: Sat ~22:30
who: Kacper
---

## What was done with AI

Had Claude Code verify Adam's review of PR #27 against the code before changing anything: ran the real `git-guard.js` on 16 commands and all 16 were allowed (push to a URL, `--delete`, `HEAD:other-branch`, `gh api .../merge`, `gh pr review --approve`, `bash -c`), then fixed it test-first: push only to `origin` and the current branch, remote rewiring and `gh` merge or approve denied with no escape, `Bash(git push origin:*)` in `allow`, `gh pr review` in `ask`

## Outcome / lesson

Agent review of the first draft had not tried to attack the hook; a human reviewer did, in a scratch repo. Then `iw-reviewer` (security focus) attacked the fix and found more that were real and reproduced: an escape written as `# IW_ALLOW_GIT=1` lifted the push checks (worse after the prompt was removed), `--del`, `--rece=x` (arbitrary program execution on real git) and `-uf` slipped past exact-match flag checks, quoted `-c` values and `git "push"` hid a redirect, `gh api` writes and glued `-R`/`-H` flags were open. Fixed test-first by turning the push flags into an allow-list and making every push and `gh` check non-escapable; 45 hook tests, mutation check on the guards: 52 tried, 52 caught (two survived at first because another guard denied the same input with a different reason, so the tests now pin the reason). The end-to-end test found a real bug the unit tests could not: `rev-parse --abbrev-ref HEAD` fails on a repo with no commits, so the hook read it as a detached HEAD. Residual risk, stated in ADR 0207: `bash -c`, scripts and editing `.git/config` still get past a text hook. The agent's own mistake, caught in Adam's second review: it had left `ask: Bash(git push:*)` in place, and an `ask` rule overrides every `allow` rule (deny, then ask, then allow), so the whole PR changed nothing; it had even written "not verified" about this instead of reading the docs. Fixed, and a test now fails if an ask or deny rule covers an allow rule (5 mutations tried, 5 caught). Lesson: read the rule-evaluation docs before changing `permissions`, not after
