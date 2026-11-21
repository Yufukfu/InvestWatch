# Spec Delta

## Purpose
Persist a parsed document safely and announce it to analytics, so downstream consumers only ever see schema-valid, deduplicated documents that are already committed.

## ADDED Requirements

### Requirement: Validate before insert
The scraper SHALL validate every document against the `ScrapedDocument` v1 schema in `contracts/` (path from `CONTRACTS_DIR`, present in the service image) before inserting it, and SHALL NOT insert an invalid one. It SHALL always set `source_id` (collected documents come from a `sources` row), because a NULL would make the dedup index treat rows as distinct.

#### Scenario: Valid document is inserted
- **WHEN** a document with all of `id, platform, url, fetched_at, text, source_kind` is ingested
- **THEN** one row exists in `documents` for it

#### Scenario: Invalid document is rejected
- **WHEN** a document is missing `text` or has a malformed `fetched_at`
- **THEN** no row is inserted and a job error with reason `schema_invalid` is recorded

### Requirement: Deduplicate by content hash
The scraper SHALL compute `content_hash` as the sha256 of the normalised text (Unicode NFC, every run of whitespace collapsed to one space, leading and trailing whitespace removed; case is preserved) and SHALL NOT insert a second document with the same `content_hash` for the same `source_id`.

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
- **THEN** the uploaded object is removed and no document row exists

### Requirement: Store raw HTML in object storage
The scraper SHALL store the fetched HTML in bucket `iw-raw` at `html/{document_id}.html` and set `html_object_key` accordingly. The scraper SHALL create the bucket at startup if it is missing. If the upload fails the document SHALL NOT be inserted.

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
