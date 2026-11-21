# Spec Delta

## Purpose
Show what the scraper collected and what failed, from the shared database alone, so scraping effectiveness can be demonstrated and checked without hand-written SQL.

## ADDED Requirements

### Requirement: Report collection per source
The scraper SHALL provide a read-only command that lists every active source with its platform, `source_kind`, `last_run_status`, `last_run_at`, total documents, documents with `fetched_at` inside the window, the latest `fetched_at`, and the job errors of the window grouped by `reason`. The window is `--since` hours (default 24).

#### Scenario: Source with documents and errors
- **WHEN** an active source has 3 documents (1 fetched inside the window) and 2 `http_error` plus 1 `timeout` job errors inside the window, and 1 older `blocked` error
- **THEN** its entry shows total 3, window 1, errors `http_error: 2, timeout: 1` and no `blocked`

#### Scenario: Source that never ran
- **WHEN** an active source has `last_run_at` NULL and no documents
- **THEN** it is listed under "never run" and under "no documents"

#### Scenario: Errors of an unknown source
- **WHEN** a job error has a `source_id` that matches no source
- **THEN** it is counted in the overall error totals and listed under "unattributed errors"

### Requirement: Report totals
The command SHALL show the document count by `platform` and by `source_kind`, the share of documents with a `html_object_key`, and the job errors of the window by `reason`, over all sources.

#### Scenario: Empty database
- **WHEN** there are no sources, documents or job errors
- **THEN** every total is zero, the share is reported as not applicable (never a division by zero) and the exit code is 0

### Requirement: Keep inactive sources apart
The command SHALL list inactive sources in a separate section and SHALL NOT count them in the "never run" and "no documents" lists.

#### Scenario: Imported sample set
- **WHEN** an inactive source holds 5 imported documents
- **THEN** it appears only in the inactive section with its document count

### Requirement: State what it cannot measure
The report SHALL NOT present a success rate over past runs, because only the last run of each source is stored. Its header SHALL say that run statuses are the last run only.

#### Scenario: Header
- **WHEN** the report is produced in either format
- **THEN** it carries the window and the note that statuses are of the last run only, and no field named or described as a success rate

### Requirement: Read only, safe output
The command SHALL only run `SELECT` statements, SHALL write its result to stdout only (diagnostics through the JSON logger), SHALL NOT include `job_errors.detail` or source URLs with credentials in its output, and SHALL exit non-zero with one redacted log line when the database is unreachable.

#### Scenario: Detail not shown
- **WHEN** a job error has a `detail` text
- **THEN** the output carries only its `reason` and counts

#### Scenario: Database down
- **WHEN** `DATABASE_URL` points at an unreachable server
- **THEN** nothing is written to stdout, one JSON error line is logged without the connection password, and the exit code is non-zero

#### Scenario: JSON format
- **WHEN** `--json` is given
- **THEN** stdout holds exactly one JSON object with the same figures as the table
