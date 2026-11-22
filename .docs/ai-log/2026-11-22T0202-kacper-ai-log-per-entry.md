---
when: Sun ~02:00
who: Kacper
---

## What was done with AI

Asked Claude Code to stop the AI log conflicting in every PR. It found why `merge=union` in `.gitattributes` did not help: GitHub ignores merge drivers when it checks whether a PR can merge, and the union merge had already duplicated one row. It then split the table into one file per entry in `.docs/ai-log/` ([ADR 0212](../decisions/0212-ai-log-one-file-per-entry.md)) and added `ai-log.mjs` with `new`, `check` (in CI) and `render`.

## Outcome / lesson

83 rows became 82 files. A script checked that the rendered table matches the old one row for row, apart from the dropped duplicate. Seven automatic slugs were meaningless (`main`, `origin`) and were renamed by hand. The fix for parallel appends is separate files, not a merge driver, as ADR 0205 already showed for status.
