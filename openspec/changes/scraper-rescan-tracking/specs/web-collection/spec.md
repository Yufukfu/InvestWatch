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
When a `web` source with a stored document answers HTTP 404 or 410 and the repeat request of the same run answers the same, the scraper SHALL store one job error with reason `gone`, the page URL in `job_errors.url` and the status in the detail. It SHALL NOT store another until a document has been stored after it. Any other status, a redirect hop, or a source with no stored document keeps its own reason.

#### Scenario: Ad removed after being stored
- **WHEN** a web source with a stored document answers HTTP 410
- **THEN** one job error with reason `gone`, the source id and the page URL is stored, and no document is produced

#### Scenario: One flaky 404
- **WHEN** a web source with a stored document answers 404 and the repeat request answers 200
- **THEN** the repeated page is processed as a normal fetch and no `gone` job error is stored

#### Scenario: Repeat answers something else
- **WHEN** the first request answers 404 and the repeat answers 503
- **THEN** the job error reason is `http_error` and no `gone` is stored

#### Scenario: Still gone on the next re-scan
- **WHEN** the next re-scan answers 404 again and no document was stored since the `gone` error
- **THEN** no second `gone` row is stored and a `rescan_outcome` line with outcome `gone` is logged

#### Scenario: Page replaced after a removal
- **WHEN** the page comes back with new text and a document is stored, and a later re-scan answers 404
- **THEN** a new `gone` job error is stored

#### Scenario: Never stored
- **WHEN** a web source that has never stored a document answers 404
- **THEN** the job error reason is `http_error`

#### Scenario: Server error is not a removal
- **WHEN** a web source with a stored document answers 503 or 403
- **THEN** the reason is `http_error` or `blocked`, never `gone`

#### Scenario: Removal lookup fails
- **WHEN** the check for stored documents fails during a 404 answer
- **THEN** the job error is recorded as `http_error`, the failure is logged and nothing else changes
