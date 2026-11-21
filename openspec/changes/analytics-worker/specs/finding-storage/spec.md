# Spec Delta

## Purpose
Persist analytics results: read a scraped document by id and store its findings so that the dashboard shows one living finding per URL and module, refreshed by re-scans. The tables are created by the API's migrations (ADR 0303); this capability only reads and writes rows. Contracts: `ScrapedDocument` and `Finding` v1 (`.docs/integration-plan.md` §3, §4).

## ADDED Requirements

### Requirement: Store interface with two implementations
Analytics SHALL access persistence only through a store interface with the operations `load_document(document_id)`, `findings_for_document(document_id)` and `save_findings(document, findings)`. A Postgres implementation and an in-memory implementation SHALL behave identically for every scenario in this spec. The worker tests run on the in-memory store.

#### Scenario: Same behaviour in both stores
- **WHEN** the storage scenario suite runs against the in-memory store, and against Postgres with `TEST_DATABASE_URL` set
- **THEN** both pass. Without `TEST_DATABASE_URL` the Postgres run is skipped, not failed.

### Requirement: Load a document
`load_document` SHALL rebuild a `ScrapedDocument` from the `documents` row by merging the `payload` JSONB with the simple columns, the columns taking precedence. It SHALL return "not found" for an unknown id. It SHALL raise a validation error, naming the field, when the row does not satisfy the model.

#### Scenario: Row with payload
- **WHEN** a row holds the contract's simple columns and `links`, `author` and `blocks` in `payload`
- **THEN** the loaded document equals the original `ScrapedDocument`

#### Scenario: Unknown id
- **WHEN** `load_document` is called with an id that has no row
- **THEN** it returns not found, and the worker maps that to `document_not_found`

#### Scenario: Invalid row
- **WHEN** the row's `text` is null
- **THEN** a validation error naming `text` is raised, and the worker maps that to `invalid_document`

### Requirement: Atomic save
`save_findings` SHALL write all findings of one document in a single transaction. Either all are committed or none is. It SHALL return each finding as persisted, with its final `id` and whether it was `created` or `updated`.

#### Scenario: Failure mid-batch
- **WHEN** writing the second of two findings fails
- **THEN** neither finding is visible after the call, and the error propagates to the worker

#### Scenario: Contract-valid rows
- **WHEN** a stored finding is read back and serialized
- **THEN** it validates against `contracts/schemas/finding.schema.json`

### Requirement: Re-scan updates instead of duplicating
A finding SHALL be identified by `(url_key, module)`, where `url_key` is the document's `canonical_url` if present, otherwise its `url`. When a finding with that key exists, `save_findings` SHALL update it in place. It SHALL keep `id`, `detected_at` and `status`, and replace `document_id`, `score`, `title`, `summary`, `firm`, `advertiser`, `rules`, `content_excerpt`, `url`, `platform`, `model` and `updated_at`. Otherwise it SHALL insert a new finding with `status: new`. Concurrent saves for the same key SHALL end with one row, enforced by a unique constraint and an upsert, not by a prior lookup alone.

#### Scenario: First scan
- **WHEN** a document from URL `U` produces an M2 finding and no finding for `(U, M2)` exists
- **THEN** a row is inserted with `status: new` and reported as `created`

#### Scenario: Re-scan of the same URL
- **WHEN** a later document from the same URL `U` produces an M2 finding with a new score
- **THEN** the existing row keeps its `id` and `detected_at`, carries the new `document_id`, score and `updated_at`, and is reported as `updated`. The table still holds one `(U, M2)` row.

#### Scenario: Analyst status survives a re-scan
- **WHEN** the existing finding has `status: confirmed` and the URL is re-scanned
- **THEN** the updated finding still has `status: confirmed`

#### Scenario: Different module, same URL
- **WHEN** one URL yields an M1 and an M2 finding
- **THEN** two rows exist, one per module

#### Scenario: Concurrent re-scans
- **WHEN** two workers save findings for the same `(url_key, module)` at the same time
- **THEN** exactly one row exists afterwards

### Requirement: Stale documents never overwrite newer results
`save_findings` SHALL NOT update a finding whose current document has a later `fetched_at` than the incoming document. Such a finding SHALL be reported as `skipped_stale` and left unchanged.

#### Scenario: Old message redelivered after a newer scan
- **WHEN** the finding for `(U, M2)` already comes from a document fetched at 15:00, and a document from `U` fetched at 14:00 is saved
- **THEN** the finding is unchanged and reported as `skipped_stale`

### Requirement: Outage surfaces as a retryable error
The Postgres store SHALL raise a distinct, retryable error type on connection loss or a serialization failure, separate from the not-found and validation outcomes. This lets the worker leave the message pending instead of treating it as poison.

#### Scenario: Database unreachable
- **WHEN** Postgres refuses connections during `load_document` or `save_findings`
- **THEN** a retryable store error is raised and no partial write remains
