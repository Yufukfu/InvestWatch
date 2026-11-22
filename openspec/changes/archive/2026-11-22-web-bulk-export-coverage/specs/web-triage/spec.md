## ADDED Requirements

### Requirement: Select findings for a bulk action
Each row of the loaded findings page SHALL have a checkbox whose accessible name includes the finding's title, and the table header SHALL have a checkbox that selects or clears every row of the page (mixed when only some are). A filter, sort or page change SHALL clear the selection, and `Esc` SHALL clear it when no detail is open. The shortcuts `J`, `K`, `O`, `1`-`5` and `/` SHALL keep working while a checkbox has focus.

#### Scenario: Select all on the page
- **WHEN** the user checks the header checkbox
- **THEN** every row of the page is checked and the bar states the page's row count; checking it again clears them; with one of several rows checked it is mixed

#### Scenario: List changes
- **WHEN** rows are selected and the user changes a filter, the sort or the page
- **THEN** no row is selected and the bar is gone

#### Scenario: Keyboard
- **WHEN** focus is on a row checkbox and the user presses `J`
- **THEN** the next finding opens as without a selection; and with no detail open, `Esc` clears the selection

### Requirement: Bulk status change
With findings selected, a bar SHALL state the count in Polish and offer one button per status, which sends `POST /findings/bulk-status` with the selected ids and that status (contracts 1.3.0), not optimistically. Success SHALL show each item's result (titles as plain text with `dir="auto"`), clear the selection and invalidate findings, stats and calibration like a single change. A failure SHALL show a Polish error and keep the selection.

#### Scenario: Select and confirm
- **WHEN** the user checks two rows and activates `Potwierdź`
- **THEN** one request is sent with those two ids in row order and status `confirmed`, and the list and the summary are fetched again

#### Scenario: Per-item results
- **WHEN** the response reports one `updated` and one `not_found`
- **THEN** the page states 1 updated and 1 not found and lists both titles with their result, and the selection is empty

#### Scenario: Request fails
- **WHEN** the bulk request returns 422 or the network fails
- **THEN** a Polish error is shown and the rows stay selected

#### Scenario: Markup in a title
- **WHEN** a selected finding's title is `<img src=x onerror=alert(1)>`
- **THEN** the checkbox name and the result list show it as text and no `img` element exists

### Requirement: M2 register coverage on the overview
The overview SHALL show the share of M2 findings matched to a KNF register entry from `m2_coverage` of `GET /stats/summary` (contracts 1.3.0) as text with both counts and the rounded percentage, plus a proportion bar of the same value that is not the only carrier of the value. A response without `m2_coverage` SHALL show `brak danych`, and `total` 0 SHALL say there are no M2 findings.

#### Scenario: Coverage present
- **WHEN** `m2_coverage` is `{ "total": 4, "registry_matched": 3 }`
- **THEN** the overview reads 3 of 4 M2 findings (75%) matched to the KNF register and the bar is filled to 75%

#### Scenario: Older server
- **WHEN** the summary has no `m2_coverage`
- **THEN** the strip reads `brak danych` and draws no filled bar

#### Scenario: No M2 findings
- **WHEN** `m2_coverage` is `{ "total": 0, "registry_matched": 0 }`
- **THEN** the strip says there are no M2 findings and draws no filled bar
