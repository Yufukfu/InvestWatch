# Tasks

## 1. Export link in the header

- [x] 1.1 Write failing tests: the header has one `Eksportuj raport`; on the findings page its `href` follows the URL filters (also after a filter change) and the truncation note uses the list total; on the overview it exports with default filters and says so; the findings page has no second copy; the `☰` button controls the export region.
- [x] 1.2 Implement `useReportExport`, `ReportExport`, the header placement, remove the findings-page copy, styles.
- [x] 1.3 Mutation check, against `App.test.tsx`: the page check on the filters dropped (URL filters on every page); the URL read once instead of subscribed (`useUrlSearch` replaced by `window.location.search`); the list query never skipped (a fetch on the overview); the total kept after an error (survived at first; test for a later failed request added, then caught); the "bez filtrów" note dropped; the cap boundary moved to `>=`; the header always told it is on the findings page; `aria-controls` without the export; the menu class never set on the export. Not counted: reading `search` from `window.location` while still calling `useUrlSearch` (the hook's subscription alone re-renders, equivalent), and `onFindingsPage &&` in the total (a skipped query has no data, equivalent). mutations: 9 tried, 9 caught

## 2. M2 rule grid

- [ ] 2.1 Write failing tests: title with N, squares in order with the rule id, legend counts for all four results, accessible names with result and legal basis, tooltip text with `dir="auto"`, `brak podstawy prawnej`, none for M1/M3 or no rules, markup stays text.
- [ ] 2.2 Implement `RuleGrid`, place it in the detail for M2, styles and contrast pairs.
- [ ] 2.3 Mutation check.

## 3. Closing

- [ ] 3.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 3.2 Run `iw-pr-review` and fix real findings.
