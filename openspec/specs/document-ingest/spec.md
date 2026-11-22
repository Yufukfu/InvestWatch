# document-ingest Specification

## Purpose

Persist a parsed document safely and announce it to analytics, so downstream consumers only ever see schema-valid, deduplicated documents that are already committed.

## Requirements

### Requirement: Validate before insert
The scraper SHALL validate every document against the `ScrapedDocument` v1 schema in `contracts/` (path from `CONTRACTS_DIR`, present in the service image) before inserting it, and SHALL NOT insert an invalid one. It SHALL always set `source_id`, because collected documents come from a `sources` row.

#### Scenario: Valid document is inserted
- **WHEN** a document with all of `id, platform, url, fetched_at, text, source_kind` is ingested
- **THEN** one row exists in `documents` for it

#### Scenario: Invalid document is rejected
- **WHEN** a document is missing `text` or has a malformed `fetched_at`
- **THEN** no row is inserted and a job error with reason `schema_invalid` is recorded

#### Scenario: Blank text
- **WHEN** the text of a document is empty or only whitespace after normalisation
- **THEN** no row is inserted and a job error with reason `empty_text` is recorded

### Requirement: Deduplicate by content hash
The scraper SHALL compute `content_hash` as the sha256 (lowercase hex, UTF-8) of the normalised text (NFC, whitespace runs collapsed, ends trimmed, case kept, compatibility characters not folded) and SHALL NOT insert a second document with the same `content_hash` for the same `source_id`. For a non-`web` document the hashed input SHALL be the `canonical_url` (else the `url`), a line feed and that text, so identical text at two permalinks is two documents.

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

#### Scenario: Compatibility characters are kept
- **WHEN** a page has the text `"ﬁnanse"`, `"m²"` or `"１２３%"` (ligature, superscript, full-width digits)
- **THEN** its `content_hash` is the sha256 of exactly that text, which differs from the hash of `"finanse"`, `"m2"` or `"123%"`

#### Scenario: Canonically equivalent text
- **WHEN** two pages differ only in composed versus decomposed form (`"\u00e9"`, U+00E9, and `"e\u0301"`, U+0065 U+0301)
- **THEN** their `content_hash` values are equal

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

### Requirement: Store raw HTML in object storage
The scraper SHALL store the fetched HTML in bucket `iw-raw` at `html/{document_id}.html` and set `html_object_key` accordingly. At startup the scraper SHALL check that the bucket exists and fail with a clear error if it does not; it SHALL NOT create it (the stack's `minio-init` does, and the app user may lack that permission). If the upload fails the document SHALL NOT be inserted. A page that has no HTML SHALL NOT be inserted either.

#### Scenario: HTML stored
- **WHEN** a document is ingested
- **THEN** the object `html/{document_id}.html` exists in `iw-raw` and `html_object_key` equals that key

#### Scenario: Page without HTML
- **WHEN** a page has no `html` (missing or blank)
- **THEN** nothing is uploaded, no `documents` row is inserted and a job error with reason `parse_error` is recorded

#### Scenario: Object storage unavailable
- **WHEN** the upload to MinIO fails
- **THEN** no `documents` row is inserted and a job error with reason `storage_error` is recorded

#### Scenario: Bucket missing
- **WHEN** the scraper starts and `iw-raw` does not exist
- **THEN** startup fails with an error naming the bucket, and the bucket is not created

### Requirement: Publish only after the database commit
The scraper SHALL publish `{"document_id": "<uuid>", "schema": "v1"}` to the Redis Stream `iw:documents` after, and only after, the `documents` row is committed.

#### Scenario: Event follows commit
- **WHEN** a new document is committed
- **THEN** an `iw:documents` entry carrying its `document_id` is published, and delivery is at-least-once (consumers deduplicate by `document_id`)

#### Scenario: Database insert fails
- **WHEN** the insert fails or rolls back
- **THEN** no `iw:documents` entry is published for it

#### Scenario: Redis unavailable after commit
- **WHEN** the row is committed but publishing fails
- **THEN** a job error with reason `publish_failed` is recorded and the document is marked as unpublished

#### Scenario: Republish sweep
- **WHEN** the republish sweep runs and Redis is available
- **THEN** every document that is unpublished and was committed longer ago than the grace period (configurable, default 60 s) is published and marked as published, and an already published document is not republished

#### Scenario: Fresh row is left alone
- **WHEN** the sweep runs while a document committed seconds ago is still being published by its own run
- **THEN** the sweep does not publish it (only the grace period protects that run; the row lock only separates sweeps)

#### Scenario: Concurrent sweeps
- **WHEN** two sweeps run at the same time over the same unpublished rows
- **THEN** each row is claimed by one of them only (row locking with skip-locked)

#### Scenario: Marker update fails after publish
- **WHEN** the stream entry was published and marking the row as published fails
- **THEN** a later sweep may publish it again, which is acceptable because consumers deduplicate by `document_id`

The schedule of the sweep is in `scan-orchestration`.

### Requirement: Author never comes from the parsed page
The scraper SHALL NOT copy `author` from a parsed page into a document, because page markup (`<meta>`, `rel=author`, embedded JSON) is controlled by the post's writer and analytics routes on `author.handle` and `author.profile_url`.

#### Scenario: Page supplies an author
- **WHEN** a parsed page carries an `author` with a firm's `profile_url`
- **THEN** the stored document has no `author`

#### Scenario: Collector passes account data
- **WHEN** a collector passes `author` explicitly
- **THEN** the stored document has exactly that `author`

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
