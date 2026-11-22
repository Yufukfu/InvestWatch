# web-triage Specification

## Purpose

How an analyst works through findings quickly: a one-click entry to the highest-risk undecided findings and keyboard shortcuts to move, decide and open the source, built only on the existing findings routes.

## Requirements

### Requirement: Triage entry
The summary SHALL offer one action, labelled `Rozpocznij triage`, that opens the findings list filtered to status `new` and risk level `high`, newest first, on page 1 with every other filter cleared, and opens the detail of the first returned row once the list has loaded. The action SHALL be absent when `GET /stats/summary` reports no high-risk findings. It SHALL NOT show a count, because that summary counts high-risk findings of every status while the triage list shows only the new ones.

#### Scenario: Start triage
- **WHEN** the summary reports 10 high-risk findings and the user activates the triage action
- **THEN** the URL carries `status=new` and `risk_level=high` (newest first is the default sort and stays out of the URL), the request uses them with `page=1`, and the detail of the first returned finding opens

#### Scenario: Nothing to triage
- **WHEN** the summary reports 0 high-risk findings
- **THEN** the triage action is not shown

#### Scenario: Triage resets other filters
- **WHEN** the user is on page 3 with module `M2`, a text search and a date range, and activates the triage action
- **THEN** the module, text, date range and page are cleared before the request is sent

#### Scenario: Triage list is empty or fails
- **WHEN** the triage request returns `total` 0 or fails
- **THEN** the list shows its normal empty or error state and no detail opens

### Requirement: Move between findings from the keyboard
While the findings section is shown and keyboard focus is not in a form field, `J` SHALL select the next finding in the loaded page and `K` the previous one. With nothing selected, `J` selects the first row and `K` does nothing. A legend of all shortcuts SHALL be reachable from the findings section.

#### Scenario: Move forward
- **WHEN** the detail of a finding is open and the user presses `J`
- **THEN** the detail of the next row opens

#### Scenario: Nothing selected
- **WHEN** no finding is selected and the user presses `J`
- **THEN** the first row is selected

#### Scenario: Start of the page
- **WHEN** `K` is pressed on the first row
- **THEN** the selection stays

#### Scenario: End of the page
- **WHEN** `J` is pressed on the last row of the page
- **THEN** the selection stays and no request for another page is made

### Requirement: Decide and open from the keyboard
With a detail open, `1`-`5` SHALL set that finding's status to `Nowe`, `W analizie`, `Potwierdzone`, `Fałszywy alarm`, `Zamknięte` through the existing status change, and send no request when it already has that status. `O` SHALL open the source link of the selected finding and `/` SHALL focus the search field. After a status change the same finding stays selected. `Esc` keeps its existing behaviour in the detail and is not handled by the shortcuts.

#### Scenario: Decide and move on
- **WHEN** the detail of a finding is open and the user presses `3`, then `J`
- **THEN** a `PATCH /findings/{id}` with status `confirmed` is sent for that finding, it stays selected until `J`, and then the next finding's detail opens

#### Scenario: No detail open
- **WHEN** no finding is selected and the user presses `1`
- **THEN** nothing happens

#### Scenario: Same status
- **WHEN** the open finding has status `confirmed` and the user presses `3`
- **THEN** no request is sent

#### Scenario: Status change fails
- **WHEN** the `PATCH` from a shortcut fails
- **THEN** the detail shows the same error as a change made with the mouse and the status shown stays the saved one

#### Scenario: Source link is unsafe
- **WHEN** the finding's URL is not `http` or `https`
- **THEN** `O` does nothing

#### Scenario: Escape is not doubled
- **WHEN** the detail is open and the user presses `Esc`
- **THEN** the existing two-step Escape of the detail applies once and the shortcuts do not also close it

### Requirement: Shortcuts never interfere with typing
Shortcuts SHALL be ignored while a text field, select or text area has focus, and when Ctrl, Meta or Alt is held, so browser and assistive-technology shortcuts keep working.

#### Scenario: Typing is not a shortcut
- **WHEN** the user types `1` in the search field
- **THEN** the character is entered and no status change is sent

### Requirement: Status shortcuts never discard unsaved edits
The `1`-`5` status shortcuts SHALL do nothing while the status editor of the open finding has unsaved changes (a status choice or a note that differs from the saved values).

#### Scenario: Unsaved note
- **WHEN** the analyst has typed a note, moved focus to `Zapisz decyzję` and presses `3`
- **THEN** no request is sent and the note stays in the editor

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
