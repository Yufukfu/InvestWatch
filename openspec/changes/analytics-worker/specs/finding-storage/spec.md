# Spec Delta

## Purpose
Persist analytics results: read a scraped document by id and store its findings, one per document and module, so that a redelivered or re-analysed document updates its finding instead of duplicating it. The tables are created by the API's migrations (`api-db-schema`, ADR 0303); this capability only reads and writes rows. Contracts: `ScrapedDocument` and `Finding` v1 (`.docs/integration-plan.md` §3, §4).

## ADDED Requirements

### Requirement: Store interface with two implementations
Analytics SHALL access persistence only through a store interface with the operations `load_document(document_id)`, `save_findings(document, findings)` and the read `findings_for_document(document_id)`. A Postgres implementation and an in-memory implementation SHALL behave identically for every scenario in this spec; the worker tests run on the in-memory store.

#### Scenario: Same behaviour in both stores
- **WHEN** the storage scenario suite runs against the in-memory store, and against Postgres with `TEST_DATABASE_URL` set
- **THEN** both pass; without `TEST_DATABASE_URL` the Postgres run is skipped, not failed

### Requirement: Load a document
`load_document` SHALL rebuild a `ScrapedDocument` from the `documents` row by merging the `payload` JSONB with the scalar columns, the columns taking precedence. It SHALL return "not found" for an unknown id, and SHALL raise a validation error naming the field when the row does not satisfy the model.

#### Scenario: Row with payload
- **WHEN** a row holds the contract scalar columns and `links`, `author` and `blocks` in `payload`
- **THEN** the loaded document equals the original `ScrapedDocument`

#### Scenario: Unknown id
- **WHEN** `load_document` is called with an id that has no row
- **THEN** it returns not found (the worker maps it to `document_not_found`)

#### Scenario: Invalid row
- **WHEN** the row's `text` is null (an empty string is valid input; the pipeline skips it as `empty_text`)
- **THEN** a validation error naming `text` is raised (the worker maps it to `invalid_document`)

### Requirement: Atomic save
`save_findings` SHALL write all findings of one document in a single transaction: either all are committed or none. It SHALL return each finding as persisted, with its final `id` and whether it was `created` or `updated`.

#### Scenario: Failure mid-batch
- **WHEN** writing the second of two findings fails
- **THEN** neither finding is visible after the call and the error propagates to the worker

#### Scenario: Contract-valid rows
- **WHEN** a stored finding is read back and serialized
- **THEN** it validates against `contracts/schemas/finding.schema.json`

### Requirement: One finding per document and module
A finding SHALL be identified by `(document_id, module)`, the unique key of `findings` in `api-db-schema`. When a finding with that key exists, `save_findings` SHALL update it in place, keeping `id`, `detected_at`, `status` and `note`, and replacing `score`, `title`, `summary`, `firm`, `advertiser` (when the model carries it), `rules`, `content_excerpt`, `url`, `platform`, `model` and `updated_at` (the `UPSERT_REPLACED` list of `api-db-schema`). Otherwise it SHALL insert a new finding with `status: new`. Concurrent saves for the same key SHALL end with one row, enforced by `INSERT ... ON CONFLICT (document_id, module) DO UPDATE`, not by a prior lookup. A changed page is a new `documents` row and therefore gets a new finding.

#### Scenario: First analysis
- **WHEN** a document produces an M2 finding and no finding for `(document_id, M2)` exists
- **THEN** a row is inserted with `status: new` and reported as `created`

#### Scenario: Same document analysed again
- **WHEN** the same document is saved again with a new score
- **THEN** the existing row keeps its `id` and `detected_at`, carries the new score and `updated_at`, is reported as `updated`, and the table still holds one `(document_id, M2)` row

#### Scenario: Analyst status and note survive
- **WHEN** the existing finding has `status: confirmed` and a note, and the document is analysed again
- **THEN** the updated finding still has `status: confirmed` and the same note

#### Scenario: Changed page
- **WHEN** a later document from the same URL (a new `documents` row) produces an M2 finding
- **THEN** a second finding is inserted for the new `document_id`; the earlier one is unchanged

#### Scenario: Different module, same document
- **WHEN** one document yields an M1 and an M2 finding
- **THEN** two rows exist, one per module

#### Scenario: Concurrent saves
- **WHEN** two workers save a finding for the same `(document_id, module)` at the same time
- **THEN** exactly one row exists afterwards, one save reported `created` and the other `updated`

### Requirement: Outage surfaces as a retryable error
The Postgres store SHALL raise a distinct retryable error type on connection loss or serialization failure, separate from not-found and validation outcomes, so the worker leaves the message pending instead of treating it as poison.

#### Scenario: Database unreachable
- **WHEN** Postgres refuses connections during `load_document` or `save_findings`
- **THEN** a retryable store error is raised and no partial write remains
