## MODIFIED Requirements

### Requirement: Columns follow the contracts
Each table SHALL store the scalar fields of its contract as typed columns and SHALL restrict every enumerated field to the values listed in `contracts/schemas/` with a CHECK constraint. `documents` SHALL keep the remaining `ScrapedDocument` fields (`author`, `links`, `media`, `screenshots`, `blocks`, `scrape_meta`) in `payload JSONB`, and SHALL reject an empty `text`. `findings` SHALL keep `firm`, `advertiser`, `rules` and `model` as JSONB columns and SHALL NOT have a `risk_level` column.

#### Scenario: Contract mock round-trips
- **WHEN** every item of `contracts/mocks/documents.json`, `findings.json` and `sources.json` is inserted and read back into the contract shape
- **THEN** each read-back object equals the mock item key by key, where a mock null reads back as null or as an absent key, only API-derived keys (`risk_level`, `documents_count`) are left out, and the object passes the contract schema

#### Scenario: Null JSONB field is SQL NULL
- **WHEN** a finding is inserted with `firm`, `advertiser` and `model` set to null
- **THEN** `firm IS NULL`, `advertiser IS NULL` and `model IS NULL` are true for that row
- **AND** a contract `null` in `firm`, `advertiser` or `model` SHALL be stored as SQL `NULL`, not as the JSON value `null`

#### Scenario: Enum checks match the contracts
- **WHEN** the CHECK constraints of the migrated database are compared with the `enum` lists of `contracts/schemas/*.json`
- **THEN** every enumerated column allows exactly the contract's values

#### Scenario: Unknown enum value is rejected
- **WHEN** a row is inserted with `platform = 'myspace'`, a finding with `module = 'M4'`, or a finding with `status = 'archived'`
- **THEN** the insert fails with a check-constraint violation and no row is stored

#### Scenario: Score out of range is rejected
- **WHEN** a finding is inserted with `score = 1.2` or `score = -0.1`
- **THEN** the insert fails with a check-constraint violation

#### Scenario: Required contract field missing
- **WHEN** a document is inserted without `text`, `url`, `platform`, `source_kind` or `fetched_at`
- **THEN** the insert fails with a not-null violation

#### Scenario: Empty document text
- **WHEN** a document is inserted with `text = ''`
- **THEN** the insert fails with a check-constraint violation
