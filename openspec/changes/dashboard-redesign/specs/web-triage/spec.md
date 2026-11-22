# Spec Delta

## Purpose
How an analyst works through findings quickly: a one-click entry to the highest-risk undecided findings and keyboard shortcuts to move, decide and open the source, built only on the existing findings routes.

## ADDED Requirements

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
