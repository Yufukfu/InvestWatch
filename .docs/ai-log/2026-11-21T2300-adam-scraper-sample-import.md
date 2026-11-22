---
when: Sat ~23:00
who: Adam
---

## What was done with AI

Claude Code planned and applied `scraper-sample-import` (`python -m iw_scraper.sample_import`: saved HTML or text through the same `Ingestor`, for the stand's samples and offline demo replay): OpenSpec change, then three task groups test-first in the image, a mutation check per group, `iw-reviewer` per group, a rehearsal of the real command on two saved pages

## Outcome / lesson

Mutation checks found three untested guards the green tests had hidden (growth after the size check, the non-zero exit code, a per-file `platform`); tests added, 14 of 14 caught per group. A teammate session's cold-read claimed per-file `source_kind` cannot work with one source per set; checked against `ingest.document.build_document` (it takes the `Source` argument), rejected, while its three other findings (author via the `author=` argument, set-name slug, a typo guard for manifest entries) were adopted. `docs-check` caught a backticked file name in a spec scenario. The full-stack rehearsal (analytics findings, dashboard alert) was skipped by the human's choice and is recorded as not done
