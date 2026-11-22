## MODIFIED Requirements

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

## ADDED Requirements

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
