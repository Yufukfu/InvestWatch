## ADDED Requirements

### Requirement: Bulk status change
`POST /api/findings/bulk-status` SHALL accept a body `{ids, status}` with 1 to 200 unique UUIDs and one status, and nothing else. In one transaction it SHALL apply to every existing id the same change as `PATCH /api/findings/{id}` with `{status}`. It SHALL return 200 with `results`, one entry per requested id in request order: `{id, result: "updated", finding}` (the finding with `risk_level`) or `{id, result: "not_found", finding: null}`, and the counts `updated` and `not_found`. After the commit it SHALL publish one `finding.updated` event `{id, status}` per updated finding. A publish failure SHALL be logged and SHALL NOT change the response.

#### Scenario: Mixed ids
- **WHEN** an analyst sends `{"ids": [a, missing, b], "status": "confirmed"}` where `a` and `b` exist
- **THEN** the response is 200 with results in the order `a`, `missing`, `b`, `updated: 2` and `not_found: 1`, both rows have `status: "confirmed"` and a later `updated_at`, and two `finding.updated` events are published

#### Scenario: Invalid bodies
- **WHEN** the body has no ids, more than 200 ids, a repeated id, a malformed id, an unknown or null status, or an extra key such as `note`
- **THEN** the response is 422, nothing is stored and no event is published

### Requirement: Report export of the findings list
`GET /api/findings/export` SHALL accept the same filters and `sort` as `GET /api/findings`, with the same validation, and `format=csv` (the default and only format). It SHALL return 200 `text/csv; charset=utf-8` with a UTF-8 BOM, a `Content-Disposition: attachment` filename, one header row and one row per matching finding in sort order, at most 10 000 rows. `X-Total-Count` SHALL hold the number of matches, and `X-Export-Truncated` SHALL be `true` when rows were cut and `false` otherwise. A text cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return SHALL get a `'` prefix.

#### Scenario: Same filters as the list
- **WHEN** a client calls `GET /api/findings/export?module=M2&status=new` and `GET /api/findings?module=M2&status=new&page_size=200`
- **THEN** the CSV rows are the list's items in the same order, with the same id, module, status, risk level and score

#### Scenario: Formula in scraped text
- **WHEN** a finding's title is `=HYPERLINK("http://x")`
- **THEN** the title cell is `'=HYPERLINK("http://x")`

#### Scenario: Invalid filter
- **WHEN** a client calls `GET /api/findings/export?status=archived` or `GET /api/findings/export?format=pdf`
- **THEN** the response is 422

### Requirement: M2 coverage counts
`GET /api/stats/summary` SHALL also return `m2_coverage` with `total`, the number of M2 findings, and `registry_matched`, the number of M2 findings whose `firm.registry_id` is not null. The other summary fields SHALL be unchanged.

#### Scenario: Matched and unmatched M2 findings
- **WHEN** there are three M2 findings, two with a `firm.registry_id` and one with `firm: null`, and one M1 finding with a `firm.registry_id`
- **THEN** `m2_coverage` is `{"total": 3, "registry_matched": 2}`

#### Scenario: Empty database
- **WHEN** there are no findings
- **THEN** `m2_coverage` is `{"total": 0, "registry_matched": 0}`
