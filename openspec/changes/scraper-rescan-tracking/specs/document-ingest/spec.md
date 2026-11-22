# Spec Delta

## ADDED Requirements

### Requirement: Report a changed page
When a document of a `web` source is inserted and the source already has an earlier document, the scraper SHALL return that document's id as `previous_document_id`, keep the outcome an insert, and log one `rescan_outcome` line with outcome `changed`. It SHALL NOT modify or delete any earlier row.

#### Scenario: Edited page
- **WHEN** a web source with one stored document is re-scanned and its text changed
- **THEN** a second row is inserted, the ingest result is an insert (the job counts one new document) with `previous_document_id` set to the first row, and a `rescan_outcome` line with outcome `changed` is logged

#### Scenario: First collection
- **WHEN** a web source with no stored document is scanned
- **THEN** one row is inserted, the result has no `previous_document_id` and no `rescan_outcome` line says `changed`

#### Scenario: Earlier rows are untouched
- **WHEN** a page is reported as changed
- **THEN** the earlier row keeps every column value it had, and no row is deleted

#### Scenario: Predecessor choice
- **WHEN** a source has three documents and a fourth is inserted
- **THEN** `previous_document_id` is the newest other row created before the new one, ties by id, and no extra event is published beyond the `iw:documents` event of the new row

#### Scenario: Lookup fails
- **WHEN** the lookup of the earlier document fails after the new row was inserted
- **THEN** the insert still counts, the result has no `previous_document_id` and the failure is logged without a job error

### Requirement: Report an unchanged or reverted re-scan
When a re-scan of a `web` source finds a duplicate, the scraper SHALL log one `rescan_outcome` line (`unchanged`, `reverted` or `reappeared`), insert nothing and publish nothing. A failing lookup is only logged.

#### Scenario: Unchanged page
- **WHEN** a re-scan finds the text of the most recent document
- **THEN** no row is inserted, no event is published and the log line outcome is `unchanged`

#### Scenario: Page returns to an earlier text
- **WHEN** a source stored text A then text B, and a re-scan finds text A again
- **THEN** no row is inserted and the log line outcome is `reverted`

#### Scenario: Page comes back after a removal
- **WHEN** a `gone` job error is newer than the most recent document and a re-scan finds that document's text
- **THEN** no row is inserted and the log line outcome is `reappeared`

#### Scenario: Duplicate after losing the insert race
- **WHEN** another worker inserted the same page between the pre-check and the insert
- **THEN** the result is a duplicate and the line is classified like any other duplicate

#### Scenario: Ties
- **WHEN** two rows of a source have the same `created_at`
- **THEN** the one with the greater id is the most recent, and "newer" always means strictly greater

#### Scenario: Non-web sources are not classified
- **WHEN** a document with a platform other than `web` is collected
- **THEN** no `rescan_outcome` line is logged for it
