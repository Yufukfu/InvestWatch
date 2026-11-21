# Spec Delta

## MODIFIED Requirements

### Requirement: One finding per document and module
A finding SHALL be identified by `(document_id, module)`, the unique key of `findings` in `api-db-schema`. When a finding with that key exists, `save_findings` SHALL update it in place, keeping `id`, `detected_at`, `status` and `note`. Otherwise it SHALL insert a new finding with `status: new`. Concurrent saves for the same key SHALL end with one row. A changed page is a new `documents` row and therefore gets a new finding.

#### Scenario: First analysis
- **WHEN** a document produces an M2 finding and no finding for `(document_id, M2)` exists
- **THEN** a row is inserted with `status: new` and reported as `created`

#### Scenario: Same document analysed again
- **WHEN** the same document is saved again with a new score
- **THEN** the existing row keeps its `id` and `detected_at`, carries the new score and `updated_at`, is reported as `updated`, and the table still holds one `(document_id, M2)` row

#### Scenario: Upsert key and replaced fields
- **WHEN** an existing finding is updated
- **THEN** exactly `score`, `title`, `summary`, `firm`, `advertiser`, `rules`, `content_excerpt`, `url`, `platform`, `model` and `updated_at` are replaced (the `UPSERT_REPLACED` list of `api-db-schema`)
- **AND** the write is `INSERT ... ON CONFLICT (document_id, module) DO UPDATE`, not a prior lookup

#### Scenario: Advertiser replaced on update
- **WHEN** the same document is saved again with a different `advertiser`
- **THEN** the row carries the new `advertiser` and reads it back; a finding without one is stored as SQL `NULL`, never JSON `'null'`

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
