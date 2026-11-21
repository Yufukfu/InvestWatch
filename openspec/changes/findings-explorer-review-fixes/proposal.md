# Proposal

## Why

Round 2 review of PR #39 by @hen68 (CHANGES_REQUESTED, https://github.com/Yufukfu/InvestWatch/pull/39#pullrequestreview-6008262488) left three blocking items in the findings detail and its tests:

1. A failed refetch after a status save changed the element type at the body slot, so React remounted the body and the status editor and focus fell to `BODY`, outside the dialog.
2. A test in `useFindings.test.tsx` ended while its request was still in flight, so it leaked into the next test under shuffled order.
3. The inert-lift-before-focus test could not fail, because jsdom ignores `inert`.

No requirement changes: the behaviour is the one already in `web-findings`; this change makes its guards and tests hold.

## What Changes

- **Detail panel keeps a stable tree:** the alert slot and the body slot are always the same two children, so a failed refetch shows the inline alert without remounting the body or the status editor.
- **Tests:**
  - a save with the refetch failing keeps focus inside the dialog;
  - the panel lifts `inert` from the page before it restores focus to the opener (spy on `focus`, check the attribute at call time);
  - the settled-search history test waits for its request to finish.

Out of scope: the non-blocking pager fix (Enter on a disabled `Następna`/`Poprzednia` button) and the `App.test.tsx` timezone flake; both are reported in the reply and not changed in this round.

Module: `web/` (Kacper). No contract, REST route or event changes.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- Code: `web/src/features/findings/components/FindingDetailPanel.tsx`, `FindingDetailPanel.test.tsx`, `web/src/features/findings/data/useFindings.test.tsx`.
