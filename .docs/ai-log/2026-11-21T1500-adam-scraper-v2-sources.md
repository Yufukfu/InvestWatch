---
when: Sat pm
who: Adam
---

## What was done with AI

Applied `scraper-v2-sources` with Claude Code stacked on the unmerged `scraper-orchestration` (PR #38): proposal cold-read by fresh agents first, then per task group a failing test (against a stub, so the red was a behaviour failure and not an import error), a mutation script that mutates a scratch copy in the test image (37 mutants for the loader and writer, 3 for the host guard) and a fresh `iw-reviewer`

## Outcome / lesson

Branch `scraper/scraper-v2-sources`. The reviewer found a real race the tests missed (the KNF insert ran outside the advisory lock, so two runs could duplicate it), an error path that could print a raw driver message, and URL credentials accepted; each was verified against the code and fixed test-first. One mutant looked like a survivor but had only broken test collection; rerun against the file tests it was caught. The seed URLs were recovered from earlier session transcripts, not from the repo, so the live check (not run yet, needs a human go-ahead) is what proves them. The edit gate asked for a facts block on every first write of a file
