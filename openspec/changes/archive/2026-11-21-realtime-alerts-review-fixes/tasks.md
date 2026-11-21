# Tasks

## 1. Toasts: announcement, focus, hold

- [x] 1.1 Announce only the arriving alert; dismiss and open leave the live line alone (review item 1).
- [x] 1.2 Keep focus inside the toast region on dismiss and open; the detail restores focus there on close (review item 3).
- [x] 1.3 Pointer and keyboard holds tracked separately; a repeated event for a held toast does not restart its timer (review item 4).

## 2. Alert data and refreshes

- [x] 2.1 Blank titles raise no toast; titles are trimmed and cut to 200 characters (review, should fix).
- [x] 2.2 Coalesce `finding.created` and `finding.high_risk` refreshes (trailing 1 s; `connect` immediate) (review, should fix).
- [x] 2.3 `finding.updated` invalidates the findings lists when a status filter is active (review, should fix).

## 3. Accessibility and language

- [x] 3.1 Close buttons named `Zamknij: <title>`; `onHold` and `onRelease` required (review, should fix).
- [x] 3.2 Scores in the Polish UI use a decimal comma in the toasts, the table and the detail panel (review, should fix).

## 4. Tests

- [x] 4.1 Mount of `AlertsPage` in `App` and the hover pause through the DOM (review item 5).
- [x] 4.2 `finding.updated` patches only the target row in every cached list (review item 5).
- [x] 4.3 Dismiss, open and close with several toasts; a duplicate event clears the old timer (review item 5).
- [x] 4.4 `isUuid`, `pushSearch` and `setSearchParam` have direct tests (review item 5).
- [x] 4.5 `realtime.integration.test.tsx` says it uses a fake socket (review item 5).

## 5. Docs

- [x] 5.1 `web/README.md` and `.docs/status/dashboard.md` describe the compose stack as it is (review, should fix).
- [x] 5.2 ADR 0208: bundle size and transitive dependencies (review, should fix).
- [x] 5.3 Archived `realtime-alerts/tasks.md`: the mutation counts 16, 8 and 14 are replaced with what was verified (review item 5).

## 6. Toasts and the detail dialog (round 2)

- [x] 6.1 While the detail dialog is open, the toasts render inside it (in its flow, not floating over Save), so they are reachable by keyboard and inside the Tab trap; a new high-risk alert is still announced there (review item 2; answered by @kacpermalczyk: "inside the dialog", "yes, announce it").
- [x] 6.2 A toast that unmounts while held (it moves between the header and the dialog) releases its holds (review item 4, follow-up to 6.1).

## 7. Held toasts that go away (round 3)

- [x] 7.1 Failing tests first: a held toast pushed out by the 4-toast cap times out when the same id arrives again; a dismissed toast that was hovered holds again when it comes back; a released toast is no longer held (review round 3, items 1 and 2).
- [x] 7.2 `useRealtime` forgets the hold and timer of every id no longer shown; `AlertToasts` drops the hover/focus reasons of every id no longer shown (review round 3, items 1 and 2).
- [x] 7.3 The dialog test renders `<App />`, so removing `ToastSlotProvider` from `App` fails it (review round 3, item 3).
- [x] 7.4 Mutation check. mutations: 4 tried, 4 caught (no prune in the hook, no prune in the toasts, `release` keeps the id held, `App` without `ToastSlotProvider`).
- [x] 7.5 ADR 0208: bundle size after the review fixes (review round 3, note).
- [x] 7.6 Race guard from the group review: the `[alerts]` effect also schedules every shown toast that is neither held nor timed, so a re-arrival that runs between the eviction render and the prune cannot leave a toast without a timer. mutations: 1 tried, 0 caught (the race needs a socket task between a commit and its passive effects, which `act()` cannot produce; traced in code, not reproduced).
- [x] 7.7 `proposal.md` describes rounds 2 and 3; the approving review's two test gaps are in `follow-ups.md`.
