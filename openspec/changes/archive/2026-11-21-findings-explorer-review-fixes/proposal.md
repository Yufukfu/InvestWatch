# Proposal

## Why

Adam's review of PR #39 (`findings-explorer`, reviewed at 9386d63) requested changes. Keyboard users lose focus on every sort, filter or page change, and again after saving a status, which escapes the dialog's focus trap. The search box drops trailing spaces while typing. Several behaviours are weak or missing (history flooding, the modal not isolating the page, Escape ignored in a filled note, the detail hidden when a refetch fails, input borders below 3:1). The test claims also overstate coverage: his independent mutation run (174 mutants) left 70 alive, and tests from the base were removed. The change `findings-explorer` is already archived, so the fixes go in this follow-up change in the same PR.

## What Changes

- **List keeps the last rows while the next page loads** (`data`, not `currentData`), marked `aria-busy`, with the pager mounted. The sort header or pager button that had focus survives.
- **Status editor resets its state instead of re-mounting** after a save, so focus stays inside the panel. The `Zapisano.` live region is always rendered. A second submit while saving is ignored.
- **Search box:** it re-syncs from the URL only when the URL differs from the trimmed local text, so "foo bar" keeps its space. Reset clears the local text, so a pending debounce cannot re-apply it. The debounced search uses `replaceState`; discrete changes keep `pushState`.
- **Detail panel:**
  - It renders in a portal. Everything else on the page is `inert` and page scroll is locked while it is open.
  - Escape in a field that holds text moves focus to `Zamknij` first, and a second Escape closes.
  - If a refetch fails, the last loaded detail stays visible with an inline error.
- **Accessibility and lint:** input and chip borders reach at least 3:1 against their background. `react/exhaustive-deps` is enabled in `web/.oxlintrc.json`.
- **Tests:**
  - restore the tests removed from `FindingsTable.test.tsx` and the full row mapping in `useFindings.test.tsx`;
  - add tests for the survivors Adam listed: double submit, page wiring (pager, page size, sort, first page), the `platform`/`q`/date request params and inputs, exact serialised param names, screenshot paths `//evil` and `/other/`, plurals 11/14/21/24, and stale detail after an id change.
  - The mutation lines in the archived `findings-explorer/tasks.md` get a note that they covered only the chosen mutants.

Out of scope: a REST backend in `docker compose up` (team-wide, see `.docs/STATUS.md`); calibration and alerts (PRs #40, #45, which receive these fixes by merge).

Module: `web/` (Kacper). No contract, REST route or event changes.

## Capabilities

### New Capabilities

### Modified Capabilities
- `web-findings`: URL history for search; modal isolation, Escape and refetch failure in the detail (MODIFIED); loading keeps the last result and the typed text, and a status save keeps focus and runs once (ADDED).

## Impact

- Code: `web/src/features/findings/**`, `web/src/url/` is not on this branch (findings data hook only), `web/src/styles.css`, `web/.oxlintrc.json`, tests.
- Docs: `.docs/status/dashboard.md`, AI log row, a note in the archived `findings-explorer/tasks.md`.
