---
when: Sun ~05:00
who: Adam
---

## What was done with AI

The user asked for slightly lighter control borders. The agent measured first: the existing border was already at the WCAG 3:1 floor (3.17 on white), so a visible change needed a decision. It asked the user (soft border with stronger hover and focus, or keep 3:1), wrote a small OpenSpec change that narrows the non-text contrast sentence, and implemented it test-first with a `--field-border` token. Same session: the data-table button was pinned to the right in both states and the pager select got the filter selects' arrow.

## Outcome / lesson

Mutation check 6 tried, 6 caught: the first run left one mutant alive (the status-editor textarea was not in the test's control list), so it was added. A Playwright reading taken right after a focus change showed a half-way colour (the 140 ms transition); waiting for it to settle gave the real value. The tradeoff (resting outline below 3:1) is recorded in the spec and design, not hidden.
