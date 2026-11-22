---
when: Sun ~00:30
who: Kacper
---

## What was done with AI

Claude Code fixed Adam's request-changes review of PR #39 in `findings-explorer-review-fixes`: verified each point against the code, wrote the failing tests first (including the cases for Adam's surviving mutants), then drove the keyboard flows in headless Chrome

## Outcome / lesson

Adam's own mutation run (174 mutants, 70 alive) showed that the agent's `mutations: N/N caught` lines counted only the mutants it had picked itself, and that earlier tests had been removed without a flag. The browser run found one more bug that jsdom passed: a `disabled` save button drops focus to `<body>` during and after a save, so it is now `aria-disabled`. Lesson: mutation lines must say they cover only the chosen mutants, and focus behaviour needs a real browser
