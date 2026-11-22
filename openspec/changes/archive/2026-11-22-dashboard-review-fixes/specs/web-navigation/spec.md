## ADDED Requirements

### Requirement: Links without a hash that address findings open the findings page
When the hash is empty or names no page and the query string contains a findings parameter (`finding`, `triage`, or a filter, sort or paging parameter of `GET /findings`), the dashboard SHALL show the findings page and set the hash to `#zgloszenia` without adding a history entry. A hash that names a page SHALL always win.

#### Scenario: Deep link to a finding
- **WHEN** the page is loaded as `/?finding=<id>` with no hash
- **THEN** the findings page and the detail of that finding are shown and the hash is `#zgloszenia`

#### Scenario: Filter-only link
- **WHEN** the page is loaded as `/?module=M1&sort=-score` with no hash
- **THEN** the findings table is shown

#### Scenario: Explicit hash wins
- **WHEN** the page is loaded as `/?finding=<id>#kalibracja`
- **THEN** the calibration page is shown
