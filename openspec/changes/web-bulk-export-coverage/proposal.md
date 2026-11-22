# Proposal

## Why

The Paper dashboard mockup shows bulk actions, a report export and an M2 coverage strip, which the redesign (`dashboard-redesign`, PR #137) left out because the API could not serve them (issue #115). The API and the mock server serve all three since PR #139 (contracts 1.3.0), and the 1.3.0 client snapshot is on `main` (#142), so the dashboard can now offer them.

## What Changes

- **Bulk status change**: each findings row gets a labelled checkbox, the table header a select-all checkbox for the loaded page (checked, unchecked or mixed), and a dark action bar (the mockup's "Masowe działania") states how many are selected and offers one button per status. A button sends `POST /findings/bulk-status` with the selected ids and that status (the generated `usePostFindingsBulkStatusMutation`), then shows the per-item results (updated / not found, in request order, titles as untrusted text with `dir="auto"`), clears the selection, and invalidates `findings`, `stats` and `calibration` exactly as the single `PATCH` does. Not optimistic. `Esc` clears the selection when no detail is open; `J`/`K`/`O`/`1`-`5` and `/` keep working (a checkbox is not a text field). The selection belongs to the loaded list: a filter, sort or page change clears it, so it never exceeds the page size (100 at most, under the API's 200 cap).
- **Report export**: the findings header gets an `Eksportuj raport` link to `<API base>/findings/export?<current list filters>&sort=<sort>` (CSV; no `page`/`page_size`), built from the same filter state and the same mapping the list request uses, with the visible note that the CSV holds at most 10 000 rows; when the list total is above 10 000 the note says the export is cut to the first 10 000.
- **M2 coverage strip**: the overview shows `m2_coverage` from `GET /stats/summary` as text (`registry_matched` of `total` M2 findings matched to the KNF register, with the percentage) and a proportion bar drawn from the same two numbers (the bar is decorative; the text carries the value). A missing field (older server) renders `brak danych`; `total` 0 renders "no M2 findings" with an empty bar.

Out of scope: PDF export, export through a fetch with progress, selection across pages, and the mockup's per-rule "Pokrycie reguł M2 · 17 wymogów" grid (the API has no per-rule counts; the strip uses the counts it has).

Module: `web/` (Kacper). Consumes REST routes `POST /findings/bulk-status`, `GET /findings/export` and the `m2_coverage` field of `GET /stats/summary` (contracts 1.3.0, already merged); touches no contract and no event.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-findings`: adds export of the filtered list.
- `web-triage`: adds bulk status change and the M2 register coverage strip on the overview.

## Impact

- Code: `web/src/api/enhanced.ts`, `web/src/features/findings/` (`FindingsPage`, `FindingsTable`, new `BulkStatusBar`, `data/useBulkStatus.ts`, `data/findingsUrl.ts`), `web/src/features/summary/` (model, hook, new `M2Coverage`), `web/src/styles.css`, tests.

Spec pre-approved by Kacper via the issue request.
