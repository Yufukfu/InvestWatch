# Tasks

## 1. Lint guard for components

- [x] 1.1 In the worktree run `npm ci` in `web/` and verify `npm run lint`, `npm run typecheck` and `npm test` pass on the unchanged code (baseline).
- [x] 1.2 Write `web/src/layering.test.ts` first: it copies the real `web/.oxlintrc.json` into a temp dir with a component file that imports `api/` and a data-hook file that does, runs the installed `oxlint`, and asserts non-zero for the component and zero for the data file. Verify it fails before the override exists.
- [x] 1.3 Add the `no-restricted-imports` override for `src/features/*/components/**` to `web/.oxlintrc.json` and verify `layering.test.ts` passes and `npm run lint` is still clean.
- [x] 1.4 Mutation check: drop one pattern (`api`), then the package entries, and verify the test fails each time; restore. Record `mutations: N tried, N caught` on this line. mutations: 4 tried, 4 caught.

## 2. Health feature

- [x] 2.1 Write failing tests: `HealthBadge` renders each state from a `state` prop without a `Provider`; `useHealth` returns `unreachable` when the request fails and `down` when the API answers `down`, using MSW and a fresh-store helper in `src/test/`.
- [x] 2.2 Create `features/health/data/useHealth.ts`, `features/health/components/HealthBadge.tsx` (props only) and `features/health/HealthPage.tsx`; render `HealthPage` in `App.tsx`; remove the old `HealthBadge.tsx`. Verify the new tests, `App.test.tsx`, `npm run lint` and `npm run typecheck` pass.
- [x] 2.3 Mutation check on the state mapping (swap `down` and `unreachable`, drop polling) and verify the tests catch it. Record `mutations: N tried, N caught`. mutations: 6 tried, 6 caught (one survived first, fixed with a no-status test).

## 3. Summary feature

- [x] 3.1 Write failing tests: `SummaryCards` renders three labelled counts from props with no `Provider` and renders nothing without data; `useSummary` returns `total`, `highRisk`, `newCount` from the contract mock.
- [x] 3.2 Create `features/summary/` (`data/useSummary.ts`, `components/SummaryCards.tsx`, `SummaryPage.tsx`), update `App.tsx`, remove the old file from `features/findings/`. Verify the new tests, `App.test.tsx`, lint and typecheck pass.
- [x] 3.3 Mutation check (swap `highRisk` and `newCount`, default missing counts to a wrong value) and verify the tests catch it. Record `mutations: N tried, N caught`. mutations: 8 tried, 8 caught.

## 4. Findings feature

- [x] 4.1 Write failing tests: `FindingsTable` renders rows, the loading text and the error alert from props with no `Provider`, and renders `<img src=x onerror=alert(1)>` as text; `useFindings` maps the contract mock to `FindingRow[]` and reports `isError` when the request fails.
- [x] 4.2 Create `features/findings/model.ts`, `data/useFindings.ts` (maps DTO to `FindingRow`, `status` and `module` assigned from the generated types), `components/FindingsTable.tsx` and `FindingsPage.tsx`; update `App.tsx`; remove the old `FindingsTable.tsx`. Verify the new tests, `App.test.tsx`, lint and typecheck pass.
- [x] 4.3 Mutation check (drop the mapping of `score`, swap `title` and `platform`, render title as HTML) and verify the tests catch it. Record `mutations: N tried, N caught`. mutations: 11 tried, 11 caught.

## 5. Closing

- [x] 5.1 Apply the `iw-docs-update` skill: update the rule file sentence about components that still call hooks directly, the dashboard row in `.docs/STATUS.md`, check `web/CLAUDE.md`; add the `iw-ai-log` row; run `docs-check` clean.
- [ ] 5.2 Run the `iw-pr-review` skill and fix real findings.

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch.
- Open the PR against the PR #11 branch; retarget to `main` once #11 merges.
