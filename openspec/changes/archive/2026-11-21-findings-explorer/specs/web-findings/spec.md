# Spec Delta

## Purpose
The findings workspace of the dashboard (`web/`): a filterable, sortable, paged list of findings, a detail view that shows why a finding is risky, and the analyst's status change. Data comes only from the backend routes in `contracts/openapi.yaml`.

## ADDED Requirements

### Requirement: Filter, sort and page the findings list
The dashboard SHALL let the user filter findings by module, status (several at once), risk level, platform, minimum score, date range and text, sort by detection time or score, and page through results. Each control SHALL send the matching `GET /findings` query parameter, and the dashboard SHALL display the `total` the backend returns without recomputing it. Every control SHALL be keyboard-operable with a visible Polish label.

#### Scenario: Filter by module and status
- **WHEN** the user selects module `M2` and the statuses `Nowe` and `W analizie`
- **THEN** the request carries `module=M2` and `status=new,in_review`, the table shows the returned rows, and the count shows the response `total`

#### Scenario: Text search is debounced
- **WHEN** the user types in the search field
- **THEN** one request with `q` is sent after typing pauses, not one per keystroke

#### Scenario: No matches
- **WHEN** the backend returns `total` 0
- **THEN** the table is replaced by a message that no finding matches, with a control that clears all filters

#### Scenario: Backend error
- **WHEN** `GET /findings` fails
- **THEN** an alert states in Polish that the findings could not be loaded, the filters stay usable and the previous result is not shown as current

### Requirement: Filter state lives in the URL
The filters, sort, page and the selected finding SHALL be kept in the URL search params under the `GET /findings` parameter names, so loading the same URL shows the same view and the browser back button restores the previous one. Invalid values SHALL be ignored.

#### Scenario: State survives a reload
- **WHEN** the user opens a URL with `?module=M1&sort=-score&page=2`
- **THEN** the controls show those values and the first request already carries them

#### Scenario: Changing a filter returns to page 1
- **WHEN** the user is on page 2 and changes the risk level filter
- **THEN** the URL and the request use `page=1`

#### Scenario: Invalid URL values
- **WHEN** the URL contains `module=M9`, `page=0` or an unknown `sort`
- **THEN** the dashboard ignores the invalid value, uses the default and does not send it to the backend

### Requirement: Findings table presents risk without relying on colour
Each row SHALL show module, title, platform, score, risk level as text (`Wysoki`, `Średni`, `Niski`) with a colour, status, and detection time, with the `risk_level` read from the response and never computed in the browser. Scraped text SHALL be rendered as text, never as HTML. Wide content SHALL scroll inside the table container instead of being cut off.

#### Scenario: Risk level text and colour
- **WHEN** a finding has `risk_level` `high`
- **THEN** its row shows the text `Wysoki` styled with the high-risk colour, and the text meets 4.5:1 contrast

#### Scenario: Untrusted markup
- **WHEN** a finding title contains `<img src=x onerror=alert(1)>`
- **THEN** the characters are shown literally and no element is created from them

#### Scenario: Narrow screen
- **WHEN** the viewport is 375 px wide
- **THEN** the table scrolls horizontally inside its container and the page itself does not

### Requirement: Finding detail
Selecting a row SHALL open a detail view and set `finding=<id>` in the URL, loaded from `GET /findings/{id}`. The view SHALL show title, summary, risk level, score, firm (name, authorised or not), advertiser if present, the document excerpt and a link to the source. The view SHALL be closable with the keyboard and return focus to the list.

#### Scenario: Deep link
- **WHEN** the page loads with `?finding=<id>`
- **THEN** the detail of that finding is open

#### Scenario: Unknown finding
- **WHEN** `GET /findings/{id}` answers 404
- **THEN** the view says in Polish that the finding does not exist and offers to close it

#### Scenario: Screenshot preview
- **WHEN** the finding's document has screenshots
- **THEN** the detail shows the desktop screenshot with a text alternative, and when the screenshot request fails it shows a short message and the rest of the detail stays usable

### Requirement: Rule results are visible
Every rule whose `result` is `fail` or `uncertain` SHALL be visible in the detail without a further click, each with `rule_id`, `name`, `severity`, `explanation`, `legal_basis` and `evidence`, exactly as the API returns them. Rules with `pass` SHALL be listed in a collapsed group that states how many there are.

#### Scenario: Failed rules are visible
- **WHEN** the detail of `contracts/mocks/finding-detail.json` opens
- **THEN** every `fail` and `uncertain` rule is on screen with its `legal_basis` and `explanation` and no expand action is needed

#### Scenario: Rule ids are not rewritten
- **WHEN** a rule has `rule_id` `R12a` or `S1.2`
- **THEN** that exact string is shown

### Requirement: Change a finding's status
The detail view SHALL let the user choose any of `new`, `in_review`, `confirmed`, `false_positive`, `closed` and add a note, and SHALL send `PATCH /findings/{id}`. The UI SHALL show the status from the response, not before it, SHALL disable the control while the request is pending, and SHALL show the API's error without changing the displayed status when the request is rejected. After success the list SHALL show the new status.

#### Scenario: Successful change
- **WHEN** the user selects `Potwierdzone`, saves, and the API answers 200 with status `confirmed`
- **THEN** the detail and the list row show `Potwierdzone`

#### Scenario: Rejected change
- **WHEN** the API answers 422 or 500
- **THEN** an alert shows an error message in Polish and the previously saved status is still displayed

#### Scenario: Keyboard operation
- **WHEN** the user uses only the keyboard
- **THEN** the status select, note field and save button are reachable in order and operable
