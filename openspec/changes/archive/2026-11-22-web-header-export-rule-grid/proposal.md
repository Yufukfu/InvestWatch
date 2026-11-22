# Proposal

## Why

PR #162 (issue #115) placed `Eksportuj raport` on the findings page and left out the mockup's "Pokrycie reguł M2" grid. The human wants both as in the Paper mockup: the export in the global header (`.docs/screens/dashboard-redesign/design/desktop-1440.jsx`, next to "Na żywo" / "System działa") and the rule grid from the components sheet (`components-1440.jsx`).

## What Changes

- **Export in the header**: the `Eksportuj raport` link moves from the findings page header to the app header (one copy). On the findings page it exports the current list: the filters are read from the URL with the findings parser (`parseFilters`), and the header re-renders on History API changes (`useUrlSearch`), so it follows every filter change. On any other page it exports with the default filters and its note says so (`Wszystkie zgłoszenia, bez filtrów`). The note keeps `CSV, maks. 10 000 wierszy.` and, when the current list total is known (findings page, same cached `GET /findings` request, no extra fetch) and above the cap, the truncation warning. Below 600 px the link sits in the menu behind `☰`, which now controls both the section links and the export. A plain link: CSV is the only format the API offers (no `⌄` menu, no PDF).
- **M2 rule grid in the detail**: for an M2 finding with rule results, the detail shows `POKRYCIE REGUŁ M2 · N WYMOGÓW` (N = rules the finding reports), a row of squares in API order, each labelled with its rule id and coloured by result, and a legend with counts: Naruszenie (`fail`), Niepewne (`uncertain`), Zgodne (`pass`), Nie dotyczy (`not_applicable`). Each square is a focusable button whose accessible name holds the rule id, the result in Polish and the legal basis; the legal basis appears in a tooltip on hover and on keyboard focus, as plain text with `dir="auto"`. The register-coverage strip on the overview stays.

Out of scope: a format menu or PDF export, a grid for M1/M3 (signals, not requirements), any change to the export query itself.

Module: `web/` (Kacper). Touches no contract, route or event: the same `GET /findings/export` link and the detail's existing `rule_results`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-findings`: the export requirement moves to the header and covers other pages; adds the M2 rule grid in the detail.

## Impact

- Code: `web/src/App.tsx`, `web/src/features/findings/` (new `ReportExport` container and `data/useReportExport.ts`, `FindingsPage`, `components/ExportReportLink.tsx`, new `components/RuleGrid.tsx`, `components/FindingDetailPanel.tsx`), `web/src/styles.css`, `web/src/styles.test.ts`, tests.

Spec pre-approved by Kacper via the issue request (follow-up asked for in the PR #162 review).
