# Tasks

## 1. Focus across module switch and save (review item 1)

- [x] 1.1 Failing tests: focus stays on the module button after a switch and on `Zapisz próg` after a save (same node, still connected); the save confirmation is announced from a live region that was already mounted. Verified red against the old `key` remount: both focus tests fail.
- [x] 1.2 Implement in `CalibrationPage` (picked threshold kept with `module` and `base`, no key) and `CalibrationPanel` (live region always rendered).
- [x] 1.3 Mutation check; mutations: 1 tried, 1 caught (the remount key restored: both focus tests fail).

## 2. Stale save and double submit (review item 2, and the guard part of item 3)

- [x] 2.1 Failing tests: a save is not sent while the thresholds are refetching after a save (`canSave` false until the read settles); a module switch is not offered while a save is in flight; two presses of `Zapisz próg` send one PUT through the page.
- [x] 2.2 Implement in `useThresholds` (`canSave = data !== undefined && !isFetching`, save guard) and `CalibrationPanel` (module buttons `aria-disabled` and ignored while saving). The page-level reset guard is removed: the panel no longer offers the switch, so it was unreachable.
- [x] 2.3 Mutation check; mutations: 3 tried, 3 caught (`canSave` without `!isFetching`: caught by the refetch test; `M2` hard-coded in the PUT body: caught by the M3 save test; the module-switch guard removed: caught by the panel test). The page-level double-submit test was not separately mutated.

## 3. Test coverage of the page and the app (review item 3)

- [x] 3.1 App mounts `CalibrationPage` (`App.test.tsx`: the heading and the M2 slider after the findings); the chunk-failure fallback has its own test file (`App.calibration-error.test.tsx`), following `App.lazy-error.test.tsx`.
- [x] 3.2 M1 and M3 saves are asserted through the page: M3 is written with the other thresholds unchanged.
- [x] 3.3 Not mutation-checked in this round: the App mount test and the chunk-failure test are written, not mutated.

## 4. Should-fix items

- [x] 4.1 `Zapisano` text: shown after a save, hidden when the slider moves, suppressed when the save also reports an error (panel tests).
- [x] 4.2 Chart and table: the chart's `aria-label` values, both markers' labels, and every table cell (precision, recall, FP, FN in their columns) are asserted.
- [x] 4.3 Marker labels: `markerSides` puts the lower value's label left and the higher value's label right (unit test in `model.test.ts`).
- [x] 4.4 Settings-read error shown in the panel (`settingsError`); other 4xx statuses get `serwer odrzucił żądanie.` (hook tests).
- [x] 4.5 One pl-PL formatter module (`format.ts`) for thresholds and percentages, in the panel, the chart and the table; the sample count reads `Liczba oznaczonych próbek: N`; the colon after `najbliższy punkt` is removed. Tests updated to `0,70` notation.
- [x] 4.6 Docs: `web/README.md` and `.docs/status/dashboard.md` describe the api service in compose and the missing `/api` proxy in the web container; archived `design.md` describes the `obecnie` comparison; the AI log row for `calibration-panel` counts five survivors (as `tasks.md` does) and a row for this round is added.
- [x] 4.7 `finding.updated` debounce and the other out-of-scope items are recorded in `follow-ups.md`.
