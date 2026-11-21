# Proposal

## Why

Review of PR #12 (hen68) found that the layering check is not a CI check yet (CI runs `npm test` only, not lint), that the lint guard misses nested component folders, file extensions and package subpaths, and that the refactor changed one visible corner (an unknown health status rendered an empty badge) and left several branches untested.

## What Changes

- A test lints the real `src/features/*/components` with the real config, so `npm test` in CI fails on a violation without touching `.github/`.
- Lint patterns: relative `data` paths at any depth, `*Page` with or without extension, package subpaths (`react-redux/**`, `@reduxjs/toolkit/**`, `socket.io-client/**`). Cases for nested folders, extensions and subpaths in `layering.test.ts`.
- `HealthBadge` falls back to the raw state for an out-of-contract value, as before the refactor.
- `HealthState` and `SummaryCounts` move to `model.ts` of their feature, so the data layer no longer imports from components.
- `useHealth` loses the test-only `pollingInterval` parameter; the 30 s interval is asserted.
- Tests: all five status labels and the fallback, page wiring of loading and error, summary through `App`, a settled-state wait instead of a sleep; `makeStore` is used by `App.test.tsx`.
- The mutation tallies are listed per mutant in the archived `tasks.md` of this change instead of bare counts.

**Out of scope:** new features, contracts, CI workflow changes, ADR 0204 text. Owner B.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-foundation`: the lint requirement now also covers nested folders and package subpaths, and requires the check to run inside `npm test`.

## Impact

- Code: `web/.oxlintrc.json`, `web/src/layering.test.ts`, `web/src/features/{health,summary}/**`, `web/src/features/findings/**` tests, `web/src/App.test.tsx`, `web/src/test/store.tsx`.
- Docs: `.claude/rules/web-dashboard.md` (types-only `model.ts` for flat DTOs), AI log row. No dependency added.
