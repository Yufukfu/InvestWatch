---
when: Sun ~01:30
who: Adam
---

## What was done with AI

Had Claude Code resume the saved `scraper-v3-render` session and apply the change test-first, one task group per commit, with a hand-written mutation script per group (about 230 mutants over the renderer, the render client, ingest and the block measurement) and an `iw-reviewer` subagent on groups 2 to 4; the end-to-end check ran the real renderer container against synthetic demo pages through the production wiring

## Outcome / lesson

The group 4 review found a real leak (a cancel during the screenshot upload left the HTML and PNG objects behind), fixed with a failing test first; mutation runs exposed weak tests (a `noscript` case that sat in `<head>` and never reached the code) and two equivalent mutants, which are listed in `tasks.md` instead of counted as caught; a page that forges `getComputedStyle` is why the block script runs in an isolated world and its output is re-validated; the saved XTB and mBank pages were not in the repository, so the demo pages are synthetic and the PR says so
