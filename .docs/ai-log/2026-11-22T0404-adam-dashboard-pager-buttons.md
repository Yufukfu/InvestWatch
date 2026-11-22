---
when: Sun ~05:10
who: Adam
---

## What was done with AI

The user reported that `Poprzednia` and `Następna` were different colours. The agent checked the code first: both are the same `.btn`, and the difference was only `disabled` on page 1 (55% opacity). It wrote a small change, a failing style test and a one-rule fix, instead of recolouring a button.

## Outcome / lesson

Mutation check 1 tried, 1 caught. The fix trades the faded look of a disabled pager button for the `disabled` attribute and the not-allowed cursor; no separate reviewer ran for the one-rule CSS change.
