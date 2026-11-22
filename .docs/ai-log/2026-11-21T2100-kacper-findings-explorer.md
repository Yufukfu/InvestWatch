---
when: Sat ~21:00
who: Kacper
---

## What was done with AI

Claude Code planned and applied `findings-explorer` (filters in the URL, detail panel, status change) test first, with a scripted mutation check per task group, then drove the app in headless Chrome (`playwright-core` against the installed Chrome) on the contract mock server at 375/768/1280 px

## Outcome / lesson

Mutation checks found 5 surviving mutants: 3 missing test cases (plural boundary, 500 is not 404, submit without a change) and 2 equivalent mutants that exposed redundant guards, removed. The browser run caught what 170 jsdom tests could not: the grid let the table widen the page on phones, and Escape stopped closing the panel after a save moved focus to `<body>`. `openspec validate --strict` failed on long requirement texts, so two requirements were split. Lesson: run the real browser at the three widths before calling layout done
