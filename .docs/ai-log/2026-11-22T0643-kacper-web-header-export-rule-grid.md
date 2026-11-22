---
when: Sun ~08:30
who: Kacper
---

## What was done with AI

PR #162 follow-up: the human asked for the two mockup points the first pass had left out, `Eksportuj raport` in the global header and the "Pokrycie reguł M2" grid. The same agent session wrote OpenSpec change `web-header-export-rule-grid`, test first, a scripted mutation check per group and `iw-reviewer` per group, under the same limits (no browser, no build, Vitest with one worker).

## Outcome / lesson

- The group review found a real bug no jsdom test could see: on a phone the export showed with the menu closed, because the base `.export-report { display: flex }` came later in `styles.css` with the same specificity as the phone `display: none`. Fixed by scoping the phone rules to `.app-header`, and pinned with a selector test in `styles.test.ts`. Lesson: for CSS-only behaviour, ask the reviewer to check the cascade, and pin selectors where jsdom cannot.
- The mutation check found that the header total survived a failed later request (RTK Query keeps the last data); a test for it was added.
- The rule grid is per finding (N = its rules), not the mockup's fixed 17, because the API reports rules per finding.
- The browser check at 375/768/1280 px is left to the parent session.
