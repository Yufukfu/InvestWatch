# realtime-alerts review fixes

## Why

Review of PR #40 (`web/realtime-alerts`) by @hen68 requested changes: the toasts re-announced an older alert when a newer one was closed, focus fell to `<body>` on dismiss or open, a repeated event restarted the timer of a held toast, a status change did not remove a row from a filtered list, blank titles raised empty toasts, and the tests let mutations of the feature survive (see the review: https://github.com/Yufukfu/InvestWatch/pull/40#pullrequestreview-6007960535). The archived change `realtime-alerts` recorded mutation counts (16, 8, 14) that the review could not reproduce; they are corrected here.

## What changes

- Toasts announce only the alert that arrived; dismissing or opening a toast does not change the live line.
- Dismissing or opening a toast moves focus to the next toast, or to the toast region when none is left; closing the detail returns focus there.
- A toast holds while hovered or focused; pointer and keyboard holds are tracked separately, and a repeated event for a held toast does not restart its timer.
- Alert titles are trimmed, must not be blank, and are cut to 200 characters.
- Refreshes triggered by `finding.created` and `finding.high_risk` are coalesced (trailing, 1 s); `connect` stays immediate.
- `finding.updated` also invalidates the findings lists when a status filter is active, because a row can leave the filter.
- Each close button has its own accessible name; `onHold` and `onRelease` are required props.
- Scores in the Polish UI use a decimal comma (`0,87`) in the toasts, the table and the detail panel.
- Tests pin the patch target, the timers, the dismiss/open order, the app mount, the hover pause through the DOM, `isUuid` and `pushSearch`/`setSearchParam`.
- Docs: `web/README.md` and `.docs/status/dashboard.md` describe the compose stack as it is now; ADR 0208 gets the measured bundle size and the transitive dependencies.

No new requirements: the behaviour in `openspec/specs/web-alerts/spec.md` stays as written. Rounds 2 and 3 (same review thread) add:

- While the detail dialog is open, the toasts render inside it and are still announced (review item 2; answered by @kacpermalczyk: "inside the dialog", "yes, announce it").
- A toast that goes away (dismissed, opened, pushed out by the cap, moved into or out of the dialog) drops its hold, its timer and its hover/focus reasons, and every shown toast is either held or timed.
