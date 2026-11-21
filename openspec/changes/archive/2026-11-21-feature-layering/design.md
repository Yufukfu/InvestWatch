# Design

## Context

Layout and rationale are decided in [ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md); the rules are in `.claude/rules/web-dashboard.md`. Current state in `web/src` (checked on this branch): `features/health/HealthBadge.tsx` (20 lines), `features/findings/SummaryCards.tsx` (21) and `features/findings/FindingsTable.tsx` (40) call `useGetHealthQuery`, `useGetStatsSummaryQuery` and `useGetFindingsQuery` directly. `App.test.tsx` renders `<App/>` with a real store and MSW handlers from `src/mocks/handlers.ts`. `src/store.ts` and that test import `api/generated`, which the ADR allows.

## Goals / Non-Goals

**Goals:**
- The three features follow the ADR layout, with identical user-visible output.
- The component-level rule is a lint failure, not reviewer discipline.

**Non-Goals:**
- New features, contract or route changes, the Recharts install.
- A view model for flat DTOs, or an abstraction over RTK Query beyond the hook.

## Decisions

- **Order: health, summary, findings.** Health is the smallest and proves the pattern (hook, props component, page, test helpers) before the one feature with a view model. Each is its own task group and commit.
- **Lint guard first.** The `no-restricted-imports` override lands before the moves, so each move is checked by it. Patterns for `src/features/*/components/**`: any path through `api/`, `data/` or `store`, plus the packages `react-redux` and `@reduxjs/toolkit`. Verified on oxlint 1.94.0: an override block reports the rule, and files outside the glob are not reported. The test copies the repo's real `.oxlintrc.json` into a temp directory with a bad and a good file and runs the installed `oxlint` there, so it checks the real config and does not write into the source tree. Alternative rejected: a committed fixture under `src/` (it would need an ignore pattern, and `--no-ignore` only covers `.eslintignore`-style ignores, not verified for config `ignorePatterns`).
- **What the hooks return.**
  - `useHealth()` returns `{ state }` with `state` one of `loading | ok | degraded | down | unreachable`. The "unreachable vs down" decision (the existing comment in `HealthBadge`) moves into the hook, because it reads RTK Query flags; the Polish label map stays in the component.
  - `useSummary()` returns the counts the cards show (`total`, `highRisk`, `newCount`) or `undefined` while loading; labels stay in the component.
  - `useFindings()` returns `{ rows, isLoading, isError }` with `rows: FindingRow[]`.
- **`FindingRow` in `features/findings/model.ts`.** Fields the table shows (`id`, `module`, `title`, `platform`, `score`, `status`). `status` and `module` are literal unions written in `model.ts`; the mapper assigns generated `Status` and `Module` to them, so a new status in the contract breaks the type check instead of passing silently. Display strings (`STATUS_LABEL`, `score.toFixed(2)`) stay in the component. Scraped text stays a plain string rendered as text.
- **Wiring names.** The wiring file is `<Name>Page.tsx` as in the ADR (`HealthPage`, `SummaryPage`, `FindingsPage`), even though the health one is a header widget; renaming is a later, cheap change. `App.tsx` renders the pages.
- **Tests.** Component tests render with props and no `Provider`. Hook tests use `renderHook` inside a fresh store per test (a small helper in `src/test/`) with MSW overrides. `App.test.tsx` is unchanged and must stay green: it is the proof that the output did not change.

## Risks / Trade-offs

- [The lint rule has false negatives, for example an import through a re-export outside the patterns] → The patterns cover `api/`, `data/` and `store` by path and the two packages by name; review keeps checking, and the rule file says so.
- [Moving files breaks relative imports silently] → `npm run typecheck` and `App.test.tsx` run after each group.
- [Stacked on PR #11, so ADR 0204 is not on `main` until #11 merges] → The PR is opened against #11's branch and retargeted to `main` after #11 merges.
