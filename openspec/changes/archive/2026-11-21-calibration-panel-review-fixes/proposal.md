# Proposal

## Why

@hen68's review of PR #45 (`calibration-panel`, reviewed at 923e054) requested changes: https://github.com/Yufukfu/InvestWatch/pull/45#pullrequestreview-6008217620

- Switching module or saving a threshold drops keyboard focus to `<body>`: the panel is re-mounted by a key, and the save feedback is inserted already filled, so it may not be announced.
- A quick save after another module's save can write a stale snapshot: the save was built from the thresholds read before the previous save's refetch, and a module switch cleared the save feedback while the PUT was in flight.
- The page wiring is unprotected: nothing tests that `CalibrationPage` is mounted by the app or its chunk-failure fallback, that M1 and M3 are saved as the shown module, or that a double submit is refused through the page.
- Smaller items: the "Zapisano" text, the chart text alternative and its table cells, the marker labels, the settings-read error, the 4xx message, number formatting and two copy issues. The docs claimed compose has no REST backend, and `design.md` and the AI log disagreed with `tasks.md`.

## What Changes

- **Focus:** the panel is no longer keyed. The picked threshold is kept with the module and the saved threshold it was chosen for, and ignored when either differs. The save feedback live region is always mounted and only its text changes.
- **Saving:** `canSave` requires a settled read (not fetching). The save ignores a call while one is in flight. Module buttons are `aria-disabled` while a save is in flight, so the save feedback is never reset under a pending PUT.
- **Errors:** a failed settings read is shown in the panel. A 4xx other than 400 and 422 gets its own message, not "błąd serwera".
- **Formatting:** one pl-PL formatter for thresholds and percentages (`0,70`, `85,7%`), in the panel, the chart and the table. Copy: the sample count reads `Liczba oznaczonych próbek: N` (no plural form needed); `najbliższy punkt (0,60)` has no colon. The marker labels are placed by order of the two values, so they do not overlap.
- **Docs:** `web/README.md` and `.docs/status/dashboard.md` say what compose does: it starts the api service, but the web container's nginx does not proxy `/api` to it yet. The archived `calibration-panel/design.md` describes the `obecnie` comparison the UI shows, not `FP 23 → 12`. The AI log row is corrected and a row for this round is added.
- **Tests:** page-level focus tests, M1 and M3 saves, a double submit through the page, the App mount and chunk-failure fallback (`App.calibration-error.test.tsx`), the refetch guard, the settings-read error, the 4xx mapping, the live region and its suppression, the table cells, the chart's marker labels and `aria-label`.

Out of scope, recorded in `follow-ups.md`: the order-dependent `useFindings` test (in PR #39), the `sync-contracts` timeout, a debounce for `finding.updated`, the wider mutation survivors of the reviewer's run, and the spec's decimal examples.

Module: `web/` (Kacper). No contract, REST route, event or requirement changes. The spec `web-calibration` is unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- Code: `web/src/features/calibration/**`, `web/src/App.test.tsx`, `web/src/App.calibration-error.test.tsx` (new).
- Docs: `web/README.md`, `.docs/status/dashboard.md`, the archived `calibration-panel/design.md`, `.docs/ai-workflow.md` (AI log).
