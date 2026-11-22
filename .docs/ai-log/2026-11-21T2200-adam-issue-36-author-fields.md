---
when: Sat ~22:00
who: Adam
---

## What was done with AI

Had Claude Code answer issue #36 (where `author.handle` / `profile_url` come from): read `origin/main` instead of the stale checkout, found that no collector sets `author` but `build_document` copied it from any parsed page, fixed that test-first in `scraper-author-provenance` and wrote the per-platform provenance table

## Outcome / lesson

Branch `scraper/scraper-author-provenance`. Verified against the code, not the docs: the first draft said the unmerged Telegram branch never maps a handle to `author`; the security review found `build_page` does, so dropping `author` outright would have stripped it, and an explicit `author=` argument was added. An existing test passed `author` through the build and had to set it after the build to keep covering the URL-scheme check. No contract edit: the `scrape_meta` flag is a proposal for the team
