# Spec Delta

## Purpose
Persist a parsed document safely and announce it to analytics, so downstream consumers only ever see schema-valid, deduplicated documents that are already committed.

## ADDED Requirements

### Requirement: Validate before insert
The scraper SHALL validate every document against the `ScrapedDocument` v1 schema in `contracts/` before inserting it, and SHALL NOT insert an invalid one.

#### Scenario: Valid document is inserted
- **WHEN** a document with all of `id, platform, url, fetched_at, text, source_kind` is ingested
- **THEN** one row exists in `documents` for it

#### Scenario: Invalid document is rejected
- **WHEN** a document is missing `text` or has a malformed `fetched_at`
- **THEN** no row is inserted and a job error with reason `schema_invalid` is recorded

### Requirement: Deduplicate by content hash
The scraper SHALL compute `content_hash` as the sha256 of the normalised text and SHALL NOT insert a second document with the same `content_hash` for the same `source_id`.

#### Scenario: Rerun of unchanged page
- **WHEN** the same page is collected twice with identical text
- **THEN** `documents` holds one row for it and no second stream event is published

#### Scenario: Changed page
- **WHEN** the page text changes between two runs
- **THEN** a second row is inserted with a different `content_hash`

### Requirement: Store raw HTML in object storage
The scraper SHALL store the fetched HTML in bucket `iw-raw` at `html/{document_id}.html` and set `html_object_key` accordingly. If the upload fails the document SHALL NOT be inserted.

#### Scenario: HTML stored
- **WHEN** a document is ingested
- **THEN** the object `html/{document_id}.html` exists in `iw-raw` and `html_object_key` equals that key

#### Scenario: Object storage unavailable
- **WHEN** the upload to MinIO fails
- **THEN** no `documents` row is inserted and a job error with reason `storage_error` is recorded

### Requirement: Publish only after the database commit
The scraper SHALL publish `{"document_id": "<uuid>", "schema": "v1"}` to the Redis Stream `iw:documents` after, and only after, the `documents` row is committed.

#### Scenario: Event follows commit
- **WHEN** a new document is committed
- **THEN** exactly one `iw:documents` entry exists carrying its `document_id`

#### Scenario: Database insert fails
- **WHEN** the insert fails or rolls back
- **THEN** no `iw:documents` entry is published for it

#### Scenario: Redis unavailable after commit
- **WHEN** the row is committed but publishing fails
- **THEN** a job error with reason `publish_failed` is recorded and the document remains retrievable for republishing
