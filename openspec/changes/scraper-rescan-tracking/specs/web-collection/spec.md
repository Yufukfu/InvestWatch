# Spec Delta

## MODIFIED Requirements

### Requirement: Never emit a document from a failed or blocked fetch
The scraper SHALL record a job error with a reason from the closed set below instead of a document when the fetch is blocked, fails, or yields no text. Block signals SHALL include HTTP 403 and 429, captcha markers and a zero-length response body. A non-block HTTP error status (for example 404 or 5xx) is `http_error` unless it is a removed page (`gone`); a body with no extractable text is `empty_text`; markup the parser cannot process is `parse_error`.

#### Scenario: Blocked response
- **WHEN** a source responds with HTTP 403, or HTTP 200 with a captcha page
- **THEN** a job error with reason `blocked` is recorded and no document is produced

#### Scenario: Timeout
- **WHEN** a single request exceeds its timeout
- **THEN** the fetch reports `timeout`

#### Scenario: HTTP error status
- **WHEN** a source responds with HTTP 500, or HTTP 404 and the source has no stored document
- **THEN** the fetch reports `http_error` and no document is produced

#### Scenario: Malformed markup
- **WHEN** the parser cannot process the fetched markup
- **THEN** a job error with reason `parse_error` is recorded and no document is produced

#### Scenario: Page with no extractable text
- **WHEN** parsing a fetched page yields empty `text`
- **THEN** a job error with reason `empty_text` is recorded and no document is produced

### Requirement: Use one closed set of job error reasons
Every job error SHALL carry exactly one reason from `blocked`, `blocked_target`, `timeout`, `http_error`, `gone`, `parse_error`, `empty_text`, `schema_invalid`, `storage_error`, `publish_failed`, `invalid_request` (a scan request or source configuration that cannot be run). The condition for each is defined in the requirement that names it.

#### Scenario: Only listed reasons can be recorded
- **WHEN** code attempts to record a job error with the reason `oops`
- **THEN** the attempt is rejected and nothing is stored under that reason

## ADDED Requirements

### Requirement: Record a removed page once, with its URL
When a `web` source with a stored document ends in HTTP 404 or 410 and one confirmation request of the same run ends the same, the scraper SHALL store one job error with reason `gone` and the source URL in `job_errors.url`. The confirmation is not a retry, and it is skipped once a `gone` error is newer than the source's newest document.

#### Scenario: Ad removed after being stored
- **WHEN** a web source with a stored document answers HTTP 410 twice in one run
- **THEN** one job error with reason `gone`, the source id and the source URL is stored, and no document is produced

#### Scenario: Redirect to a removed page
- **WHEN** the source URL redirects to a page that answers 404 twice
- **THEN** the job error is `gone` and its URL is the source URL

#### Scenario: One flaky 404
- **WHEN** a web source with a stored document answers 404 and the confirmation answers 200
- **THEN** the confirmation's page is processed as a normal fetch and no `gone` job error is stored

#### Scenario: Confirmation answers something else
- **WHEN** the first request answers 404 and the confirmation answers 503, or 429
- **THEN** the job ends with that answer's own reason, `http_status` and `Retry-After`, and no `gone` is stored

#### Scenario: Still gone on the next re-scan
- **WHEN** a `gone` error is newer than the newest document and the next re-scan answers 404
- **THEN** one request is made, no second `gone` row is stored and a `rescan_outcome` line with outcome `gone` is logged

#### Scenario: Page replaced after a removal
- **WHEN** the page comes back with new text and a document is stored, and a later re-scan answers 404 twice
- **THEN** a new `gone` job error is stored

#### Scenario: Never stored
- **WHEN** a web source that has never stored a document answers 404
- **THEN** the job error reason is `http_error` and no confirmation is made

#### Scenario: Server error is not a removal
- **WHEN** a web source with a stored document answers 503 or 403
- **THEN** the reason is `http_error` or `blocked`, never `gone`

#### Scenario: Removal lookup fails
- **WHEN** the check for stored documents fails during a 404 answer
- **THEN** the job error is recorded as `http_error`, the failure is logged and nothing else changes

#### Scenario: URL is redacted
- **WHEN** the source URL carries userinfo or a token query
- **THEN** the stored `job_errors.url` shows neither, and is cut to a fixed maximum length

### Requirement: A removal is a success for the domain pause
A run that ends with `gone` SHALL be recorded as a success outcome for the domain, because the site answered normally, and a `gone` outcome SHALL NOT count toward the failure pause.

#### Scenario: Gone does not pause the domain
- **WHEN** five consecutive jobs for one domain end with `gone`
- **THEN** the domain is not paused

#### Scenario: Other failures still count
- **WHEN** five consecutive jobs for one domain end with `http_error` 503
- **THEN** the domain is paused as before
