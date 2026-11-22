# Tasks

## 1. Report export link

- [ ] 1.1 Write failing tests: `exportUrl` builds `<API base>/findings/export` with the list filters (same mapping as `toQueryArg`), `sort` always, never `page`/`page_size`; the findings page shows `Eksportuj raport` with that `href` and the 10 000-row note, and the truncation note above 10 000.
- [ ] 1.2 Implement `exportUrl` and the link with its note. Tests, lint, typecheck.
- [ ] 1.3 Mutation check.

## 2. M2 coverage strip

- [ ] 2.1 Write failing tests: `useSummary` maps `m2_coverage` (or leaves it undefined); `M2Coverage` shows counts and percentage with a bar, `brak danych` when missing, the no-M2 text when `total` is 0.
- [ ] 2.2 Implement the view model, the hook mapping, the component on the overview and its styles.
- [ ] 2.3 Mutation check.

## 3. Bulk status change

- [ ] 3.1 Write failing tests: row and select-all checkboxes (names, mixed state), the bar with the count and status buttons, the request body, per-item results, cache invalidation of findings and stats, error keeps the selection, a filter change clears it, `Esc` clears it with no detail open, `J` works from a checkbox, untrusted titles stay text.
- [ ] 3.2 Implement `useBulkStatus`, `enhanced.ts` invalidation, selection in `FindingsPage`, checkboxes in `FindingsTable`, `BulkStatusBar`, `Esc` in `useFindingShortcuts`, styles.
- [ ] 3.3 Mutation check.

## 4. Closing

- [ ] 4.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 4.2 Run `iw-pr-review` and fix real findings.
