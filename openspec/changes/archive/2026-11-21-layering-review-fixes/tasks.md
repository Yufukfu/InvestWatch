# Tasks

## 1. Lint guard

- [x] 1.1 Write failing tests first in `web/src/layering.test.ts`: nested component importing another feature's data hook, `../DemoPage.tsx`, `react-redux/es/x`, `@reduxjs/toolkit/dist/query/react`, `socket.io-client/dist/x` are rejected; a test that lints the real `src/features/*/components` expects exit 0, and a scratch copy of a real component with an added `api/` import is rejected. Verify they fail first.
- [x] 1.2 Update the patterns in `web/.oxlintrc.json`; verify the tests, `npm run lint` and `npm run typecheck` pass.
- [x] 1.3 Mutation check: drop each pattern group in turn; list every mutant and result on this line. Mutants, each drop of one pattern from the group in `web/.oxlintrc.json`: `**/api`, `**/api/**`, `../**/data`, `../**/data/**`, `**/*Page`, `**/*Page.*`, `**/store`, `**/store.*`, `react-redux`, `react-redux/**`, `@reduxjs/toolkit`, `@reduxjs/toolkit/**`, `socket.io-client`, `socket.io-client/**`. First run: 4 survived (`**/api`, `../**/data`, `**/store.*`, `socket.io-client`: no bare-form cases); cases added, rerun. mutations: 14 tried, 14 caught.

## 2. Health and summary types

- [x] 2.1 Write failing tests: `HealthBadge` renders the raw value for an unknown state; polling is asserted as `pollingInterval: 30000` (mocked generated hook, own test file); `useSummary` failure test waits for the settled state; all five status labels and the fallback are asserted in `FindingsTable`.
- [x] 2.2 Move `HealthState` and `SummaryCounts` to `model.ts`, restore the label fallback, drop the `pollingInterval` parameter; verify tests, lint, typecheck.
- [x] 2.3 Mutation check on the label fallback, the interval and the status labels; list every mutant and result on this line. Mutants: drop `?? state` in `HealthBadge`; `POLL_MS` 30 s to 60 s; drop the polling option; status label `new` reworded; `confirmed` swapped to another label; `closed` replaced; drop `?? f.status` in `FindingsTable`; `useSummary` returns zeros instead of `undefined` without data. mutations: 8 tried, 8 caught.

## 3. Wiring tests

- [x] 3.1 Add `FindingsPage`, `SummaryPage` and `HealthPage` tests (loading, error, data through a real store) and a summary case in `App.test.tsx`; `App.test.tsx` and tests use `makeStore` from `test/store.tsx`.
- [x] 3.2 Mutation check on the page wiring (drop `isError`, `isLoading`, swap props); list every mutant and result on this line. Mutants: `FindingsPage` `isLoading` forced false, `isError` forced false, `rows` forced undefined; `SummaryPage` data forced undefined; `HealthPage` state forced `ok`; `App` without `SummaryPage`; `App` without `HealthPage`; `FindingsTable` `isError ||` dropped. `isError` forced false in `FindingsPage` survived: it is only observable on a failed refetch with stale rows, so the table-level case (`isError` with rows) was added and kills the table mutant; the page mutant stays equivalent with these fixtures. mutations: 8 tried, 7 caught, 1 equivalent (documented).

## 4. Closing

- [x] 4.1 Apply `iw-docs-update`: `.claude/rules/web-dashboard.md` wording for types-only `model.ts`, AI log row, `docs-check` clean.
- [x] 4.2 Run `iw-pr-review`; fix real findings.

## Workflow follow-up

- Archive as the last commit, push, update the PR body (counts), reply to the review.

## Review follow-ups (iw-pr-review)

- `SummaryPage` failure test waited only for the request to be sent; it now waits for the settled failure in the store. Mutant: an error `<p>` rendered on failure is caught. mutations: 1 tried, 1 caught.
- Not fixed, recorded: an alias import (`@/features/x/data/y`) would bypass the patterns (no alias exists in the repo yet; extend the patterns when one is added); the polling test pins the exact call shape of the mocked hook; CI still has no separate `lint`/`typecheck` step (workflow change, owner Kacper).
