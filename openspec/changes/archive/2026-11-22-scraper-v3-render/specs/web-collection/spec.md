## MODIFIED Requirements

### Requirement: Use one closed set of job error reasons
Every job error SHALL carry exactly one reason from `blocked`, `blocked_target`, `timeout`, `http_error`, `parse_error`, `empty_text`, `schema_invalid`, `storage_error`, `publish_failed`, `invalid_request` (a scan request or source configuration that cannot be run), `render_failed` (a failed render step that did not end in a block, a refused target or a storage error; defined by `page-rendering`). The condition for each is defined in the requirement that names it.

#### Scenario: Only listed reasons can be recorded
- **WHEN** code attempts to record a job error with the reason `oops`
- **THEN** the attempt is rejected and nothing is stored under that reason

#### Scenario: Render failure has its own reason
- **WHEN** the renderer is unreachable during a run
- **THEN** the job error is recorded with the reason `render_failed`, which the closed set accepts and which is stored as text in `job_errors.reason` without a database migration
