---
when: Sun ~07:00
who: Kacper
---

## What was done with AI

Issue #115, web part: one agent session built the bulk status change, the `Eksportuj raport` CSV link and the M2 coverage strip against the 1.3.0 client already on `main`, from a brief that named the Paper mockup sources (`.docs/screens/dashboard-redesign/design/components-1440.jsx`, `desktop-1440.jsx`), Damian's field shapes in the issue and a hard resource cap (8 GB machine: no docker, no `vite build`, Vitest with one worker). OpenSpec change `web-bulk-export-coverage`, failing test first per group, a scripted mutation check per group (snippet asserted, file restored), and the `iw-reviewer` agent on each group's range.

## Outcome / lesson

- The mutation check found that the first selection design (selection stored with its list key and read as empty for another key) brought an old selection back when the user returned to the same filters; the spec says a filter change clears it. Fixed by resetting the state during render when the key changes; one survivor then showed the read-time key check had become redundant, so it was removed.
- A CSS comment mentioning `issue #115` failed the design-token test (`#115` reads as a hex colour). Comments in `styles.css` now avoid issue numbers.
- Two mutants were equivalent (an `|| false` no-op the agent wrote, and the `return` after `Esc`, since no other branch matches `Escape`); recorded as such in `tasks.md`, not counted as caught.
- Not done by the agent: a visual check in a browser at 375/768/1280 px (no dev server allowed on the machine). The human should look at the bulk bar and the coverage strip before the demo.
