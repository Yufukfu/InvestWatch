# Spec Delta

## MODIFIED Requirements

### Requirement: Filter state lives in the URL
The filters, sort, page and the selected finding SHALL be kept in the URL search params under the `GET /findings` parameter names, so loading the same URL shows the same view and the browser back button restores the previous one. Invalid values SHALL be ignored. A settled text search SHALL replace the current history entry instead of adding one.

#### Scenario: State survives a reload
- **WHEN** the user opens a URL with `?module=M1&sort=-score&page=2`
- **THEN** the controls show those values and the first request already carries them

#### Scenario: Changing a filter returns to page 1
- **WHEN** the user is on page 2 and changes the risk level filter
- **THEN** the URL and the request use `page=1`

#### Scenario: Invalid URL values
- **WHEN** the URL contains `module=M9`, `page=0` or an unknown `sort`
- **THEN** the dashboard ignores the invalid value, uses the default and does not send it to the backend

#### Scenario: Search does not flood history
- **WHEN** the user types a search and then changes the module
- **THEN** the history has one new entry for the module change and none for the search

### Requirement: Finding detail
Selecting a row SHALL open a detail view and set `finding=<id>` in the URL, loaded from `GET /findings/{id}`. The view SHALL show title, summary, risk level, score, firm (name, authorised or not), advertiser if present, the document excerpt and a link to the source. The view SHALL be modal: the rest of the page is inert and does not scroll while it is open. It SHALL be closable with the keyboard and return focus to the list.

#### Scenario: Deep link
- **WHEN** the page loads with `?finding=<id>`
- **THEN** the detail of that finding is open

#### Scenario: Unknown finding
- **WHEN** `GET /findings/{id}` answers 404
- **THEN** the view says in Polish that the finding does not exist and offers to close it

#### Scenario: Screenshot preview
- **WHEN** the finding's document has screenshots
- **THEN** the detail shows the desktop screenshot with a text alternative, and when the screenshot request fails it shows a short message and the rest of the detail stays usable

#### Scenario: Escape in a filled field
- **WHEN** focus is in the note field holding unsaved text and the user presses Escape
- **THEN** focus moves to `Zamknij` and the text is kept, and a second Escape closes the view

#### Scenario: Refetch fails
- **WHEN** the detail was loaded and a later refetch of it fails
- **THEN** the last loaded detail stays visible with an inline Polish message that it could not be refreshed

## ADDED Requirements

### Requirement: Loading keeps the last result and the typed text
While a new page, sort or filter loads, the findings list SHALL keep showing the last result marked busy, and the pager SHALL stay mounted, so the control that had keyboard focus is not removed. The search box SHALL keep the text exactly as typed.

#### Scenario: Focus survives a sort or page change
- **WHEN** a keyboard user activates the `Wynik` sort header or `Następna strona`
- **THEN** the table and pager stay mounted with `aria-busy` while the next result loads, and focus stays on that control

#### Scenario: Typed text is kept
- **WHEN** the user types `foo bar` into the search box, pausing after `foo `
- **THEN** the box shows `foo bar` and the request carries `q=foo bar`

#### Scenario: Reset beats a pending search
- **WHEN** the user types and presses `Wyczyść filtry` before the search settles
- **THEN** the search box is empty and no request with the typed `q` is sent

### Requirement: Saving a status keeps focus and runs once
After a status change is saved, keyboard focus SHALL stay inside the detail view, and the confirmation SHALL be announced through a live region that is always present. While a save is pending, further submits SHALL be ignored.

#### Scenario: Focus after save
- **WHEN** the user saves a status with the keyboard and the API answers 200
- **THEN** focus is still inside the detail view, not on the page body, and `Zapisano.` is in the live region

#### Scenario: Double submit
- **WHEN** the form is submitted again while the first request is pending
- **THEN** only one `PATCH` is sent
