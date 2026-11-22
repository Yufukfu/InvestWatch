# Tasks

## 1. Report export link

- [x] 1.1 Write failing tests: `exportUrl` builds `<API base>/findings/export` with the list filters (same mapping as `toQueryArg`), `sort` always, never `page`/`page_size`; the findings page shows `Eksportuj raport` with that `href` and the 10 000-row note, and the truncation note above 10 000.
- [x] 1.2 Implement `exportUrl` and the link with its note. Tests, lint, typecheck.
- [x] 1.3 Mutation check, each against `findingsUrl.test.ts` and `FindingsPage.test.tsx`: `sort` dropped from the export params; `page` added to them; the `undefined` guard dropped (every key written); `score_min` misnamed; the truncation boundary `>` moved to `>=`; the truncation note never shown; `download` dropped. The `%2C` to `,` rewrite is not mutated: both forms decode to the same value (equivalent mutant). mutations: 7 tried, 7 caught

## 2. M2 coverage strip

- [x] 2.1 Write failing tests: `useSummary` maps `m2_coverage` (or leaves it undefined); `M2Coverage` shows counts and percentage with a bar, `brak danych` when missing, the no-M2 text when `total` is 0.
- [x] 2.2 Implement the view model, the hook mapping, the component on the overview and its styles.
- [x] 2.3 Mutation check, against `src/features/summary`: `brak danych` emptied; the `total === 0` branch disabled; the clamp to 100% dropped; the clamp to 0% dropped; the singular boundary moved to 2; the bar fill drawn with no value; the bar exposed to assistive technology; `registry_matched` mapped from `total`; a missing field mapped to zeros instead of undefined; the strip removed from the overview. mutations: 10 tried, 10 caught

## 3. Bulk status change

- [x] 3.1 Write failing tests: row and select-all checkboxes (names, mixed state), the bar with the count and status buttons, the request body, per-item results, cache invalidation of findings and stats, error keeps the selection, a filter change clears it, `Esc` clears it with no detail open, `J` works from a checkbox, untrusted titles stay text.
- [x] 3.2 Implement `useBulkStatus`, `enhanced.ts` invalidation, selection in `FindingsPage`, checkboxes in `FindingsTable`, `BulkStatusBar`, `Esc` in `useFindingShortcuts`, styles.
- [x] 3.3 Mutation check, against `FindingsPage.test.tsx` and `useBulkStatus.test.tsx`: selection reset on a list change dropped; success-only clear made unconditional; select-all `every` turned into `some`; `Esc` clear never offered; the no-detail guard on `Esc` dropped; `indeterminate` never set; header `checked` true for any selection; checkbox name without the title; the API title and the sent title each dropped from the result name; ids sent in reverse order; the old error kept on a new request; `dismiss` a no-op; bulk invalidation reduced to `findings`; the saving guard on the buttons dropped (survived at first; test for one request while saving added, then caught); the bar shown with 0 selected; `dir="auto"` dropped from result titles; `Wyczyść zaznaczenie` a no-op. A survivor showed the read-time list-key check was redundant after the reset, so it was removed. Equivalent, not counted: an `|| false` no-op, and the `return` after `Esc` (no later branch matches `Escape`). mutations: 18 tried, 18 caught

## 4. Closing

- [x] 4.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [x] 4.2 Run `iw-pr-review` and fix real findings. Group reviews (3) and the whole-branch review: no blocking findings. Could not check: a visual run in a browser, Gitleaks locally (not installed; CI runs it).
