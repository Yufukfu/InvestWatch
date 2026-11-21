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
