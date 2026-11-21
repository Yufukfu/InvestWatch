# Tasks

## 1. Chart: accessibility, dash patterns, time labels

- [x] 1.1 Write failing tests in `TrendChart.test.tsx`: dash pattern per line path and legend swatch, legend shows totals, a table lists every bucket, no focusable element inside the image, `role="status"` on loading, labelled bucket group, local hour ticks with the date at local midnight (`Asia/Tokyo`), UTC day ticks in `America/Los_Angeles` and `Asia/Tokyo` with "Dni liczone w czasie UTC.". Verify they fail first.
- [x] 1.2 Implement in `TrendChart.tsx`; move `TrendBucket`/`TrendPoint` to `model.ts`; nits (tooltip animation, test names, `overflow-x`, smoke test); `App.test.tsx` counts rows of the findings table only, since the trend section now has its own table. Verify tests, lint, typecheck.
- [x] 1.3 Mutation check; list every mutant and result on this line. Mutants in `TrendChart.tsx`, each run against `components/`: dash removed from `<Line>`; dash removed from the legend swatch; `SERIES` M2 dash `undefined`; M3 dash equal to M2; `accessibilityLayer` on; legend without totals; table drops the last row; table cell shows M1 for every module; loading without `role="status"`; bucket group without its label; hour ticks in UTC; no date at local midnight; midnight check on UTC hours; day ticks in local time; full hour label without the date; UTC note for hours too; UTC note never shown; missing count `?? 1`; `hasData` with `every`. mutations: 19 tried, 19 caught.

## 2. Data: day mock, stale data, lazy page

- [x] 2.1 Write failing tests: `TrendPage` with a delayed day handler shows loading and not the hourly totals under `Dzień`; a refetch of the same bucket (`stats` invalidated) keeps the chart instead of flashing the loading text; the default handlers answer `bucket=day` with UTC-day sums; `App` renders the lazy trend section. Verify they fail first.
- [x] 2.2 Implement the day aggregation in `mocks/handlers.ts` and the lazy `TrendPage`; verify tests, lint, typecheck, `contracts:check`, build.
- [x] 2.3 Mutation check; list every mutant and result on this line. Mutants: `useTrend` loading from `isFetching` alone; `data` instead of `currentData`; loading from `!currentData` alone; handler ignores `bucket`; handler keys days by the full timestamp; handler drops the M2 sum; handler sums M3 from M2; `App` without `TrendPage`; trend section swapped before the summary. First run: `isFetching` alone survived (only visible on a refetch with data on screen); the refetch case was added, rerun. Lazy loading itself is checked by `vite build` (separate `TrendPage` chunk), not by a mutant. mutations: 9 tried, 9 caught.

## 3. Closing

- [x] 3.1 Apply `iw-docs-update`: `.docs/integration-plan.md` §5 matches OpenAPI, ADR 0203 note, `.docs/STATUS.md`, AI log row, `docs-check` clean.
- [ ] 3.2 Run `iw-reviewer` on the branch; fix real findings.
