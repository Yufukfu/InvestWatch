# Spec Delta

## MODIFIED Requirements

### Requirement: Derive run status and record it on the source
`data.status` SHALL be `ok` with no job error (`gone` excluded), `failed` with no document and at least one job error, otherwise `partial`. When a job starts running the scraper SHALL set `sources.last_run_status` to `running`; at its final outcome it SHALL write `last_run_at` (UTC) and `last_run_status`. `scan.finished.documents` is the job's new documents; there is no `documents_count` column (the API counts rows on read).

#### Scenario: Run ends with job errors
- **WHEN** a job ends with one document and one job error
- **THEN** `scan.finished` has `status = partial` and `sources.last_run_status = partial`

#### Scenario: Run produces nothing
- **WHEN** the fetch of a job fails with a block
- **THEN** `scan.finished` has `status = failed`, `documents = 0`, and `last_run_at` is set

#### Scenario: Last run counts
- **WHEN** a second job for the same source finds only duplicates
- **THEN** `scan.finished` has `documents = 0` and `status = ok`

#### Scenario: Removed page ends ok
- **WHEN** a job ends with a `gone` job error and no document
- **THEN** `scan.finished` has `status = ok`, `documents = 0` and `sources.last_run_status = ok`

## ADDED Requirements

### Requirement: A removed page is neither retried nor a domain failure
A run that ends with `gone` SHALL NOT be retried and SHALL be recorded as a success for the domain's failure pause, because the site answered normally.

#### Scenario: Gone is not retried
- **WHEN** a job ends with `gone`
- **THEN** it is not requeued and its attempt counter is cleared

#### Scenario: Gone does not pause the domain
- **WHEN** five consecutive jobs for one domain end with `gone`
- **THEN** the domain is not paused

#### Scenario: Other failures still count
- **WHEN** five consecutive jobs for one domain end with `http_error` 503
- **THEN** the domain is paused as before
