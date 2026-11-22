---
when: Sun ~04:30
who: Adam
---

## What was done with AI

After PR #137 was opened the user asked for real sub-pages for `#przeglad`, `#zgloszenia` and `#kalibracja`, more space above the chart data-table button and a deep modern-styling pass. A small OpenSpec change (`dashboard-subpages-polish`) was written first; routing was done test-first in the main worktree while a subagent did the CSS audit in a separate git worktree (it only touched `styles.css` and its test), then its two commits were cherry-picked.

## Outcome / lesson

Routing mutation check 8 tried, 8 caught; polish mutation check 10 tried, 10 caught. Six existing tests assumed the one-page layout and were updated to start on the right hash. The whole-branch reviewer on the first PR found an unisolated search text in the filter chip, fixed test-first. The polish subagent's Sonnet screenshot review mixed real points with wrong ones (it called the intentional hamburger a missing nav); the agent kept only what the code confirmed.
