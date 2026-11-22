---
when: Sun ~12:00
who: Adam
---

## What was done with AI

A Claude Code session wrote the scraper slides of the hand-in (`.docs/presentation-scraper.md`, issues #77 and #74), docs-only: every number recomputed from `origin/main`, `git show --numstat` and `gh`, then `iw-reviewer` on the range for factual accuracy After #128 merged, the reviewer found slide 3 still said X and YouTube were not merged; the slides were updated from the merged code.

## Outcome / lesson

Branch `chore/presentation-scraper`. The brief said the renderer PR was not on `main`; `gh pr view 67` showed it merged at 00:24 and the status file still said "PR pending", so both were fixed from the evidence. "Add a collector in N lines" is true for a source (7 TOML lines, `b3b37bd`) but the one real collector commit (`49ca3e6`) is +247 source lines and +464 test lines, and the slide says so. Redaction exists three times (`logs.py`, `reporting.py`, `ingest/errors.py`), not twice as the status file said.
