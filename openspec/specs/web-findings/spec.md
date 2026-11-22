# web-findings Specification

## Purpose

The findings workspace of the dashboard (`web/`): a filterable, sortable, paged list of findings, a detail view that shows why a finding is risky, and the analyst's status change. Data comes only from the backend routes in `contracts/openapi.yaml`.

## Requirements

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

### Requirement: Untrusted text is escaped plain text
Finding fields written by a model or copied from scraped pages (`title`, `summary`, `rule_results[].explanation`, `rule_results[].evidence`, `advertiser.name`, `advertiser.handle`, the document excerpt and text) SHALL be rendered verbatim as escaped plain text in the findings table and the detail: never as HTML or Markdown, never through `dangerouslySetInnerHTML`, and URLs inside them SHALL NOT become links.

#### Scenario: Markup in evidence and explanation
- **WHEN** a finding's evidence, explanation, summary, title and advertiser name and handle contain `<img src=x onerror=alert(1)>` and `[link](javascript:alert(1))`
- **THEN** both strings are shown literally, no `img` element exists in the detail, and no link with a `javascript:` URL or the text `link` exists

#### Scenario: Bare URL in evidence
- **WHEN** the evidence contains `https://evil.example/x`
- **THEN** it is shown as text and the only links in the detail are the export link, the source link and the advertiser profile

### Requirement: Untrusted text has its own direction
Each untrusted value listed above SHALL be shown in an element that holds only that value and has `dir="auto"`, so a quote in any language gets its own direction and a bidi control inside it cannot reorder the UI text around it.

#### Scenario: Right-to-left override
- **WHEN** the evidence, explanation, summary, title, advertiser name or handle contains U+202E
- **THEN** each U+202E is inside an element with `dir="auto"` whose text is exactly that field's value, and the closing quote mark of the evidence and the separator before a collapsed rule's explanation are outside that element

#### Scenario: Title in the table
- **WHEN** a row's title contains U+202E
- **THEN** the title button has `dir="auto"` and its text is exactly the title

### Requirement: Server error detail has its own direction
When a status change is rejected and the API returns its own error text, that text SHALL be shown alone in an element with `dir="auto"` (and `lang="en"`), outside the Polish label `Odpowiedź serwera:`, so a bidi control in it cannot reorder the label.

#### Scenario: Right-to-left override in the server detail
- **WHEN** the API rejects a status change with an error text that contains U+202E
- **THEN** the text is shown in an element with `dir="auto"` whose text is exactly the error text, and `Odpowiedź serwera:` is outside that element

### Requirement: Rows show the source host
Each findings row SHALL show the host of the finding's `url` as text, and the list SHALL keep one row per finding, never merged or deduplicated by URL or document.

#### Scenario: Host as text
- **WHEN** a finding's `url` is `https://example.com/post/1?x=<b>`
- **THEN** its row shows `example.com` as text

#### Scenario: Unusable URL
- **WHEN** a finding's `url` is not an http(s) URL
- **THEN** its row shows no host and the rest of the row is unchanged

#### Scenario: Two modules on one post in the list
- **WHEN** the response holds an M1 and an M3 finding with the same `document_id`
- **THEN** both are shown as separate rows, each with its own status

### Requirement: Detail shows every module of the material
When a finding's detail is open, the dashboard SHALL load the findings of the same document with `GET /findings?document_id=<document_id>` and, when there is more than one, SHALL show a keyboard-operable module switcher listing each module with its risk level as text. Choosing a module SHALL set `finding=<id>` in the URL and show that finding's rules, score, risk and analyst decision, while the source, excerpt and screenshot stay shown once.

#### Scenario: Switch from M1 to M3
- **WHEN** the detail of an M1 finding is open and its document also has an M3 finding
- **THEN** the switcher shows `M1` (current) and `M3`, and activating `M3` sets `finding=<M3 id>`, shows the M3 rules and decision, and keeps focus on the switcher

#### Scenario: Single module
- **WHEN** the document has only the open finding
- **THEN** no switcher is shown

#### Scenario: Sibling request fails
- **WHEN** the `GET /findings?document_id=…` request fails
- **THEN** no switcher is shown, the detail of the open finding stays fully usable, and no error replaces it

#### Scenario: Deep link and back
- **WHEN** the user switches from M1 to M3 and presses the browser back button
- **THEN** the M1 detail is shown again

#### Scenario: Module filter does not hide siblings
- **WHEN** the list is filtered to `M1` and the user opens an M1 finding whose document also has M3
- **THEN** the switcher still offers `M3`, because the sibling request carries no module filter

### Requirement: Export a finding's evidence pack
The finding detail SHALL offer an `Eksportuj` link that opens the printable evidence pack of that finding, `GET /findings/{id}/export?format=html` (contracts 1.2.0), under the app's API base URL, in a new tab. The link SHALL be shown only while that finding's detail is loaded, and it SHALL be keyboard-reachable inside the modal detail.

#### Scenario: Loaded detail
- **WHEN** the detail of a finding is loaded
- **THEN** the header shows a link named `Eksportuj` whose `href` is `<API base>/findings/<id>/export?format=html` and which opens in a new tab with `rel="noopener noreferrer"`

#### Scenario: Not loaded or unknown
- **WHEN** the detail is still loading, failed to load with no earlier data, or the finding does not exist (404)
- **THEN** no `Eksportuj` link is shown

### Requirement: Re-scan state in the finding detail
The finding detail SHALL show the re-scan state that `GET /findings/{id}` serves as `document.scrape_meta.rescan` (`rest-api` "Finding detail with its document"): a text badge `Zmieniona` with a Polish line naming `latest_document_id` for `changed`, a text badge `Usunięta` with a Polish line for `removed`, each with `checked_at` in UTC, and nothing otherwise. The web SHALL parse `scrape_meta` as untrusted data and show only a known state, a UUID id and a valid timestamp.

#### Scenario: Page changed after the finding
- **WHEN** the detail has `rescan` `{state: "changed", latest_document_id: <uuid>, checked_at: <time>}`
- **THEN** the panel shows the badge `Zmieniona`, a line naming `<uuid>` as the newer version, and the check time in UTC

#### Scenario: Page removed after the finding
- **WHEN** the detail has `rescan` `{state: "removed", latest_document_id: null, checked_at: <time>}`
- **THEN** the panel shows the badge `Usunięta` and a line that the page was removed

#### Scenario: No re-scan data (mock mode)
- **WHEN** the detail comes from `contracts/mocks/finding-detail.json`, which has no `scrape_meta.rescan`, or `rescan.state` is `current`
- **THEN** the panel shows no re-scan badge or line

#### Scenario: Malformed re-scan data
- **WHEN** `rescan` is a string, has an unknown `state`, a `latest_document_id` that is not a UUID, or a `checked_at` that is not a timestamp
- **THEN** an unknown state shows no badge, and the invalid id or time is left out of the line instead of being shown

### Requirement: Export the filtered list
The app header SHALL offer one `Eksportuj raport` link to `GET /findings/export` (contracts 1.3.0) under the API base. On the findings page it SHALL carry the current list's filters and `sort` from the URL, as the list request sends them, without `page`/`page_size`; on other pages the default filters, saying so. It SHALL state the 10 000-row cap and warn when the known list total exceeds it.

#### Scenario: Filtered list
- **WHEN** the findings page is filtered to module `M2`, status `new,in_review`, risk `high`, platform `web`, score at least 0.5, dates 2026-11-01 to 2026-11-21, text `forex`, sorted by `-score`, on page 3 with page size 50
- **THEN** the header link's `href` is `<API base>/findings/export?` with `module=M2`, `status=new,in_review`, `risk_level=high`, `platform=web`, `score_min=0.5`, `date_from=2026-11-01T00:00:00Z`, `date_to=2026-11-21T23:59:59Z`, `q=forex`, `sort=-score`, and no `page` or `page_size`

#### Scenario: Unfiltered list
- **WHEN** the findings page has no filter set
- **THEN** the link's `href` is `<API base>/findings/export?sort=-detected_at`

#### Scenario: Filter change
- **WHEN** the user changes a filter on the findings page
- **THEN** the header link follows it without a reload

#### Scenario: Another page
- **WHEN** the overview is shown, even with findings filters left in the URL
- **THEN** the link's `href` is `<API base>/findings/export?sort=-detected_at` and its note says it exports every finding without filters

#### Scenario: Above the cap
- **WHEN** the findings list total is 12 000
- **THEN** the note says the export holds only the first 10 000 of 12 000 findings

#### Scenario: List failed
- **WHEN** the list request fails
- **THEN** the link is still shown with the current filters and the general 10 000-row note, without a total

#### Scenario: Phone
- **WHEN** the screen is below 600 px wide
- **THEN** the link is in the menu opened by the `☰` button, which reports `aria-expanded` and controls it

### Requirement: M2 rule grid in the detail
The detail of an M2 finding with rule results SHALL show `POKRYCIE REGUŁ M2 · N WYMOGÓW` (N = its number of rules), one square per rule in API order showing the rule id, and a legend with the count of each result: Naruszenie (`fail`), Niepewne (`uncertain`), Zgodne (`pass`), Nie dotyczy (`not_applicable`). Each square SHALL be focusable, named with the rule id, the result in Polish and the legal basis, and SHALL show the legal basis as plain text with `dir="auto"` on hover and on keyboard focus.

#### Scenario: M2 detail
- **WHEN** an M2 finding has 10 rules: 8 `fail` and 2 `pass`
- **THEN** the grid is titled `POKRYCIE REGUŁ M2 · 10 WYMOGÓW`, has 10 squares in API order, and the legend reads Naruszenie 8, Niepewne 0, Zgodne 2, Nie dotyczy 0

#### Scenario: Square name and tooltip
- **WHEN** a square is for rule `R2` with result `fail` and legal basis `art. 24 ust. 3 MiFID II`
- **THEN** its accessible name contains `R2`, `Naruszenie` and `art. 24 ust. 3 MiFID II`, and its tooltip shows the legal basis as text with `dir="auto"`

#### Scenario: No legal basis
- **WHEN** a rule has no legal basis
- **THEN** its name and tooltip say `brak podstawy prawnej`

#### Scenario: Not M2 or no rules
- **WHEN** the finding is M1 or M3, or an M2 finding has no rules
- **THEN** no grid is shown

#### Scenario: Markup in the legal basis
- **WHEN** a legal basis is `<img src=x onerror=alert(1)>`
- **THEN** it is shown as text and no `img` element exists in the grid
