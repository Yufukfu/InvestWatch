# Design

## Context

- Mockup: `.docs/screens/dashboard-redesign/design/components-1440.jsx` ("Masowe działania": a navy bar, `Zaznaczono N zgłoszenia`, `Esc — wyczyść zaznaczenie`, status buttons; "Pokrycie reguł M2") and `desktop-1440.jsx` (`Eksportuj raport` as an outlined button at the top right).
- The API shapes are in issue #115 (Damian's comment) and `contracts/openapi.yaml` 1.3.0; `web/src/api/generated.ts` already has `postFindingsBulkStatus`, `getFindingsExport` and `m2_coverage`.
- Production CSP is `style-src 'self'`: data widths go through React's `style` prop (dashboard-redesign design decision 7).

## Decisions

1. **Selection lives in `FindingsPage`, keyed by the list URL.** State is `{ key, ids }` where `key` is the list's filters serialized without the selected finding; a different key reads as an empty selection. So a filter, sort or page change clears it without an effect, and the selection is always a subset of one loaded page (page size at most 100, below the API's 1-200). Alternative: keep ids across pages. Rejected: the user cannot see what is selected on other pages, and the bar would need a second count.
2. **Bulk mutation in a data hook `useBulkStatus`** over the generated mutation; `enhanced.ts` gives `postFindingsBulkStatus` the same `invalidatesTags` as the single PATCH (`findings`, `stats`, `calibration`). The result is mapped to a view model (`BulkResult`) with the titles captured from the rows at send time, so a `not_found` item (finding `null`) still has a name. Errors reuse the status editor's Polish messages (`toSaveError`, now exported).
3. **Esc clears the selection only when no detail is open**: added to `useFindingShortcuts` behind `selectedId === undefined`, so the detail's two-step Escape stays its only handler while it is open. A checkbox is already not "typing" there, so `J`/`K`/`O`/`1`-`5` keep working with focus on a checkbox.
4. **Export is a plain link** (`<a href download>`), not the generated `getFindingsExport` query: the browser handles the attachment. The URL comes from `exportUrl(filters)` in `findingsUrl.ts`, which reuses `toQueryArg` (the same mapping as the list request, dates expanded the same way) and drops `page` and `pageSize`; `sort` is always written. Placement: the findings page header, next to the heading, since the filters live there (the mockup's global header has no list context on the other pages).
5. **Coverage strip on the overview**, under the KPI row: one line of text with the numbers and the percentage, and a bar whose fill is the same proportion (`aria-hidden`; the text is the value, so colour or length alone carries nothing). The mockup's 17-rule grid needs per-rule counts the API does not have.

## Risks / Trade-offs

- The CSV link cannot show the `X-Export-Truncated` header; the note uses the list total, which comes from the same filters, to warn when the cap applies.
- Selecting rows and then opening a detail with `J`/`K` keeps the selection (same list key), by design.
