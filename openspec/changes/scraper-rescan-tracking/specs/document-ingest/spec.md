# Spec Delta

## ADDED Requirements

### Requirement: Report a changed page
When a document of a `web` source is inserted and the same source already has at least one earlier document, the scraper SHALL report the result as changed, naming the id of the most recent earlier document, and SHALL log one `rescan_outcome` line with outcome `changed`. It SHALL NOT modify or delete any earlier row, and SHALL NOT publish anything beyond the normal `iw:documents` event for the new row. The first document of a source is not a change.

#### Scenario: Edited page
- **WHEN** a web source with one stored document is re-scanned and its text changed
- **THEN** a second row is inserted, the ingest result is `changed` with the id of the first row, and a `rescan_outcome` line with outcome `changed` is logged

#### Scenario: First collection
- **WHEN** a web source with no stored document is scanned
- **THEN** one row is inserted, the result is a plain insert and no `rescan_outcome` line says `changed`

#### Scenario: Earlier rows are untouched
- **WHEN** a page is reported as changed
- **THEN** the earlier row keeps every column value it had, and no row is deleted

#### Scenario: Lookup fails
- **WHEN** the lookup of the earlier document fails after the new row was inserted
- **THEN** the insert still counts, the result is a plain insert and the failure is logged without a job error

### Requirement: Report an unchanged or reverted re-scan
When a re-scan of a `web` source finds a duplicate, the scraper SHALL log one `rescan_outcome` line: `unchanged` when the matching row is the source's most recent document, `reverted` when it is an older one, and `reappeared` when a `gone` job error is newer than the most recent document. A duplicate SHALL still insert nothing and publish nothing.

#### Scenario: Unchanged page
- **WHEN** a re-scan finds the text of the most recent document
- **THEN** no row is inserted, no event is published and the log line outcome is `unchanged`

#### Scenario: Page returns to an earlier text
- **WHEN** a source stored text A then text B, and a re-scan finds text A again
- **THEN** no row is inserted and the log line outcome is `reverted`

#### Scenario: Page comes back after a removal
- **WHEN** a `gone` job error is newer than the most recent document and a re-scan finds that document's text
- **THEN** no row is inserted and the log line outcome is `reappeared`

#### Scenario: Non-web sources are not classified
- **WHEN** a document with a platform other than `web` is collected
- **THEN** no `rescan_outcome` line is logged for it
