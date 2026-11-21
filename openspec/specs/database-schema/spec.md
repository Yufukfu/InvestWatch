# database-schema Specification

## Purpose
One migrated Postgres schema that the scraper, analytics and the API share, so every service writes and reads the v1 contracts (`.docs/integration-plan.md` §3-§4) through the same tables, constraints and conflict rules. Owned by `api/` (Alembic).

## Requirements

### Requirement: Migrations own the schema
The `api` service SHALL create and change every shared table only through Alembic revisions under `api/migrations/`, applied as the admin role (`iw_admin`). No other service and no init script SHALL create or alter these tables.

#### Scenario: Empty database is migrated
- **WHEN** `alembic upgrade head` runs against an empty `investwatch` database as `iw_admin`
- **THEN** the tables `sources`, `documents`, `findings`, `job_errors` and `calibration_points` exist and `alembic current` reports the head revision

#### Scenario: Migration is idempotent
- **WHEN** `alembic upgrade head` runs a second time on a migrated database
- **THEN** it exits 0 and changes nothing

#### Scenario: Downgrade removes the tables
- **WHEN** `alembic downgrade base` runs on a migrated database with no other objects
- **THEN** none of the five tables exist and `alembic upgrade head` recreates them

#### Scenario: Application role has CRUD but no DDL
- **WHEN** a service connected as `iw_app` inserts, selects, updates and deletes a row in each table, then tries `CREATE TABLE` or `ALTER TABLE`
- **THEN** the CRUD statements succeed and the DDL statements fail with a permission error

### Requirement: Migration step runs before writers start
The `api/compose.yaml` file SHALL define a one-shot `api-migrate` service that runs `alembic upgrade head` and exits, so that the scraper, analytics and the API can start only after it completed successfully. The root `compose.yaml` SHALL include `api/compose.yaml`, and `api/compose.yaml` SHALL use the `postgres` service and the data network that `infra/compose.yaml` defines without redeclaring that network's name.

#### Scenario: Stack starts on an empty volume
- **WHEN** `docker compose up` starts from the root `compose.yaml` with an empty Postgres volume
- **THEN** `api-migrate` exits 0 after Postgres is healthy and before any service that depends on it starts

#### Scenario: Migration fails
- **WHEN** `alembic upgrade head` fails (for example Postgres is unreachable or the admin password is wrong)
- **THEN** `api-migrate` exits non-zero, logs the error as JSON without the password, and the services that depend on it do not start

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

### Requirement: Documents are deduplicated per source
`documents` SHALL have a unique index on `(source_id, content_hash)` that treats a null `source_id` as one value and ignores rows whose `content_hash` is null, so that `INSERT ... ON CONFLICT (source_id, content_hash) WHERE content_hash IS NOT NULL DO NOTHING` drops a repeated document while any other conflict (for example a reused `id`) still fails.

#### Scenario: Same text from the same source
- **WHEN** two documents with the same `source_id` and the same `content_hash` are inserted with that statement
- **THEN** `documents` holds one row and the second insert returns no row

#### Scenario: Same text from two sources
- **WHEN** two documents with the same `content_hash` but different `source_id` are inserted
- **THEN** both rows are stored

#### Scenario: Ad-hoc documents without a source
- **WHEN** two documents with `source_id = null` and the same `content_hash` are inserted with that statement
- **THEN** `documents` holds one row

#### Scenario: Documents without a hash
- **WHEN** two documents with the same `source_id` and `content_hash = null` are inserted
- **THEN** both rows are stored

#### Scenario: Reused document id
- **WHEN** a second document with a different `content_hash` reuses the `id` of an existing one
- **THEN** the insert fails with a primary-key violation instead of being dropped as a duplicate

#### Scenario: Unknown source
- **WHEN** a document is inserted with a `source_id` that has no row in `sources`
- **THEN** the insert fails with a foreign-key violation

### Requirement: Published-to-stream marker
`documents` SHALL have a nullable `stream_published_at` timestamp that is null until the document has been announced on Redis Stream `iw:documents`, and an index that makes the query "unpublished documents, oldest first" use it.

#### Scenario: New document is unpublished
- **WHEN** a document is inserted without `stream_published_at`
- **THEN** it is returned by the unpublished-documents query

#### Scenario: Marked document leaves the sweep
- **WHEN** `stream_published_at` is set on a document
- **THEN** the unpublished-documents query no longer returns it

#### Scenario: Sweep query uses the index
- **WHEN** `EXPLAIN` runs the unpublished-documents query on a table with 10 000 published and 10 unpublished rows
- **THEN** the plan uses the partial index on unpublished rows, not a sequential scan

### Requirement: One finding per document and module
`findings` SHALL be unique on `(document_id, module)`, so that analysing the same document again updates its finding instead of inserting a second one. The documented upsert SHALL keep the existing `id`, `detected_at`, `status` and `note` and SHALL replace the analysis fields and `updated_at`.

#### Scenario: Re-scan of the same document
- **WHEN** a finding for `(document_id, 'M2')` exists with `status = 'in_review'` and a note, and the documented upsert runs for the same pair with a new score and rules
- **THEN** `findings` still holds one row for the pair with the original `id`, `detected_at`, `status` and note, and the new `score`, `rules` and `updated_at`

#### Scenario: Different modules on one document
- **WHEN** an M1 and an M2 finding are inserted for the same document
- **THEN** both rows are stored

#### Scenario: Finding for a missing document
- **WHEN** a finding is inserted with a `document_id` that has no row in `documents`
- **THEN** the insert fails with a foreign-key violation

### Requirement: Indexes for the dashboard queries
`findings` SHALL have indexes that serve the REST filters and sorts of `GET /findings` and `GET /stats/trend` (`detected_at` descending, `module`, `status`, `platform`, `score`), and `job_errors` SHALL be indexed by `(source_id, occurred_at)`.

#### Scenario: Default list query uses an index
- **WHEN** `EXPLAIN` runs the default findings page query (newest 50 by `detected_at`) on 10 000 findings
- **THEN** the plan uses an index on `detected_at`, not a sort over a sequential scan

### Requirement: Job errors table
`job_errors` SHALL store one row per scraper failure with `id`, optional `source_id`, `url`, a non-empty `reason`, optional `detail` and `occurred_at`. `source_id` SHALL have no foreign key, so an error about a source that has no `sources` row (for example a scan request naming an unknown source) is still recorded. The table SHALL NOT have columns for credentials, proxy URLs or request headers.

#### Scenario: Error is recorded
- **WHEN** the scraper inserts a job error with `reason = 'blocked'` for a source
- **THEN** it can be read back by `source_id`, newest first

#### Scenario: Error for an unknown source is recorded
- **WHEN** the scraper inserts a job error with `reason = 'invalid_request'` and a `source_id` that has no row in `sources`
- **THEN** the row is stored and can be read back by that `source_id`

#### Scenario: Empty reason is rejected
- **WHEN** a job error is inserted with an empty `reason`
- **THEN** the insert fails with a check-constraint violation

### Requirement: Calibration points table
`calibration_points` SHALL store one row per `(run_id, module, threshold)` with the counts `tp, fp, fn, tn`, `precision`, `recall`, optional `f1`, `labeled_samples` and `computed_at`, matching the point shape of `GET /calibration` in `contracts/openapi.yaml`.

#### Scenario: Latest run per module
- **WHEN** two runs for `M2` are stored with different `computed_at`
- **THEN** the query "points of the latest run for M2, by threshold" returns only the newer run's points in ascending threshold order

#### Scenario: Duplicate point in one run
- **WHEN** a second point with the same `(run_id, module, threshold)` is inserted
- **THEN** the insert fails with a unique violation
