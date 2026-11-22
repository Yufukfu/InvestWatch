---
when: Sat ~19:00
who: Kacper
---

## What was done with AI

Had Claude Code split `.docs/STATUS.md` into one status file per domain (`.docs/status/`) after the team agreed to it: measured the cause (module rows of 168-1076 characters, 35 commits to one file), moved the content into bullets without rewriting it, wrote ADR 0205 and updated every place that stated the old "own row" rule (CLAUDE.md, SDLC, two skills, OpenSpec config, INDEX)

## Outcome / lesson

`docs-check` caught bare file names in backticks as broken references; stale claims (`api/` missing) were dropped only after checking the tree. Docs-only chore, no OpenSpec change (`IW_SKIP_SPEC=1`)
