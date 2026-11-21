## MODIFIED Requirements

### Requirement: Deduplicate by content hash
The scraper SHALL compute `content_hash` as the sha256 of the normalised text (Unicode NFC, every run of whitespace collapsed to one space, leading and trailing whitespace removed; case is preserved) and SHALL NOT insert a second document with the same `content_hash` for the same `source_id`. For a document whose `platform` is not `web` (a post, where `url` is the permalink of one item), the hashed input SHALL be the `canonical_url` when the document has one, otherwise the `url`, then a line feed and the normalised text, so that identical text posted at two permalinks of one source is two documents while share or tracking parameters on one permalink do not make a second one. The value is still a lowercase sha256 hex string, so the schema pattern, the `ck_documents_content_hash` check and the `(source_id, content_hash)` unique index are unchanged.

#### Scenario: Rerun of unchanged page
- **WHEN** the same page is collected twice with identical text
- **THEN** `documents` holds one row for it and no second stream event is published

#### Scenario: Whitespace-only difference
- **WHEN** two pages have the texts `"Zysk  do 20%\n"` and `"Zysk do 20%"`
- **THEN** both have `content_hash` equal to the sha256 of `Zysk do 20%`

#### Scenario: Case difference
- **WHEN** two pages differ only in letter case
- **THEN** their `content_hash` values differ

#### Scenario: Changed page
- **WHEN** the page text changes between two runs
- **THEN** a second row is inserted with a different `content_hash`

#### Scenario: Duplicate leaves no stray object
- **WHEN** an unchanged page is collected again and the document is a duplicate
- **THEN** no object is added to `iw-raw` (any object uploaded before the duplicate was detected is removed)

#### Scenario: Insert fails for another reason
- **WHEN** the HTML was uploaded and the insert then fails with an error other than a duplicate
- **THEN** a job error with reason `storage_error` is recorded, and the uploaded object is removed if the insert certainly did not commit; if the insert may have committed (a dropped connection, a timeout, a cancellation) the object is kept and logged as `possible_orphan`, so that no document row points at a missing object

#### Scenario: Same text at two permalinks
- **WHEN** two documents of one source have `platform = other`, the same text and the urls `https://t.me/h/1` and `https://t.me/h/2`
- **THEN** their `content_hash` values differ and both rows are inserted

#### Scenario: Same post collected again
- **WHEN** a document with `platform = other` is collected twice with the same url and text
- **THEN** one row exists for it

#### Scenario: Tracking parameter on the permalink
- **WHEN** two documents with `platform = other` have the same text and `canonical_url`, and `url` values that differ only by a query parameter
- **THEN** their `content_hash` values are equal and one row exists

#### Scenario: No canonical URL
- **WHEN** a document with `platform = other` has no `canonical_url`
- **THEN** the `url` is hashed with the text

#### Scenario: Web page hash is unchanged
- **WHEN** a document with `platform = web` is hashed
- **THEN** the hash is the sha256 of the normalised text alone, as before
