---
when: Sun 03:09
who: Kacper
---

## What was done with AI

A Claude Code agent drafted Kacper's part of the hand-in package (issue #77): the dashboard and architecture slides plus a click-by-click demo and 3-minute video script (`.docs/presentation-dashboard.md`), and the title, Polish and English description, PDF slide order and human checklist (`.docs/hand-in.md`). Prompt approach that worked: read the challenge's §4, §6 and §8 first, copy every UI label from `web/src/` instead of describing the UI from memory, and take real-data numbers only from the #78 rehearsal comments and gold-set numbers only from the analytics slides.

## Outcome / lesson

Branch `chore/hand-in-package`, docs only. Checking against the code removed claims the first draft leaned towards: there is no per-source filter (platform plus text search), no export button in the dashboard, and the dashboard was never rehearsed on real data, so the demo's predicted card change after saving the M2 threshold (eMakler 0.39 drops to medium) is marked as a prediction from rounded #78 scores. Also found: the root README Quick Start is stale about the api, and removing `doc/` would break links in `.docs/INDEX.md` and the README; both are on the human checklist. PDF export, video and upload stay with the human.
