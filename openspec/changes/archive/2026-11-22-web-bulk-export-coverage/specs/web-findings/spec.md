## ADDED Requirements

### Requirement: Export the filtered list
The findings page SHALL offer an `Eksportuj raport` link to `GET /findings/export` (contracts 1.3.0) under the app's API base URL, whose query carries exactly the filters of the current list request (same names and values, dates expanded the same way) and its `sort`, without `page` or `page_size`. The page SHALL state that the CSV holds at most 10 000 rows, and when the current list total exceeds 10 000 it SHALL say that the export holds only the first 10 000.

#### Scenario: Filtered list
- **WHEN** the list is filtered to module `M2`, status `new,in_review`, risk `high`, platform `web`, score at least 0.5, dates 2026-11-01 to 2026-11-21, text `forex`, sorted by `-score`, on page 3 with page size 50
- **THEN** the link's `href` is `<API base>/findings/export?` with `module=M2`, `status=new,in_review`, `risk_level=high`, `platform=web`, `score_min=0.5`, `date_from=2026-11-01T00:00:00Z`, `date_to=2026-11-21T23:59:59Z`, `q=forex`, `sort=-score`, and no `page` or `page_size`

#### Scenario: Unfiltered list
- **WHEN** no filter is set
- **THEN** the link's `href` is `<API base>/findings/export?sort=-detected_at`

#### Scenario: Above the cap
- **WHEN** the list total is 12 000
- **THEN** the page says the export holds only the first 10 000 of 12 000 findings

#### Scenario: List failed
- **WHEN** the list request fails
- **THEN** the link is still shown with the current filters and the general 10 000-row note, without a total
