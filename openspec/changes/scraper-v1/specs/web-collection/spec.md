# Spec Delta

## Purpose
Turn an active registered web source into the parsed fields of a `ScrapedDocument` (`.docs/integration-plan.md` §3), or into a recorded job error when the page cannot be trusted.

## ADDED Requirements

### Requirement: Collect active sources only
The scraper SHALL run a collection job for each `sources` row with `active = true` and `platform = web`, and SHALL skip every other row.

#### Scenario: Inactive source is skipped
- **WHEN** a collection run starts and a source has `active = false`
- **THEN** no request is made to that source's URL

#### Scenario: Non-web source is skipped
- **WHEN** a collection run starts and an active source has a `platform` other than `web`
- **THEN** no request is made and no job error is recorded for it

### Requirement: Parse a fetched page into contract fields
For a successful fetch the scraper SHALL produce `url`, `canonical_url`, `fetched_at` (UTC ISO-8601), `http_status`, `title`, `text` (clean text of the page), `links`, `platform`, `source_kind` and `scrape_meta`. `source_kind` SHALL be copied from the `sources` row, never inferred from the page.

#### Scenario: Article page is parsed
- **WHEN** a saved fixture of a normal article page is parsed
- **THEN** `text` is non-empty, `title` matches the page title, and every `links[].href` is an absolute URL

#### Scenario: Source kind comes from the source row
- **WHEN** a source row has `source_kind = firm_own`
- **THEN** the resulting document has `source_kind = firm_own` regardless of page content

### Requirement: Never emit a document from a failed or blocked fetch
The scraper SHALL record a job error with a reason (`blocked`, `timeout`, `http_error`, `parse_error`, `empty_text`) instead of a document when the fetch is blocked, fails, or yields no text. Block signals SHALL include HTTP 403 and 429, captcha markers and an empty body.

#### Scenario: Blocked response
- **WHEN** a source responds with HTTP 403, or HTTP 200 with a captcha page
- **THEN** a job error with reason `blocked` is recorded and no document is produced

#### Scenario: Timeout
- **WHEN** a request exceeds its timeout after the configured retry cap
- **THEN** a job error with reason `timeout` is recorded and no document is produced

#### Scenario: Page with no extractable text
- **WHEN** parsing a fetched page yields empty `text`
- **THEN** a job error with reason `empty_text` is recorded and no document is produced

### Requirement: Be polite to sources
The scraper SHALL honour `robots.txt` and `Retry-After`, SHALL apply a configurable per-domain rate limit, and SHALL keep one identity (proxy, user agent, header set, TLS profile) fixed within a session.

#### Scenario: Disallowed by robots.txt
- **WHEN** `robots.txt` of a source's domain disallows the target path
- **THEN** the page is not fetched and a job error with reason `blocked` is recorded

#### Scenario: Retry-After is honoured
- **WHEN** a source answers 429 with `Retry-After: 30`
- **THEN** the next request to that domain starts no earlier than 30 seconds later

### Requirement: Treat scraped content as untrusted
The scraper SHALL store scraped text verbatim, SHALL NOT execute or template it, and SHALL NOT fetch any URL taken from scraped content unless its domain is on the configured allow-list.

#### Scenario: Link to a non-allow-listed host is not followed
- **WHEN** a parsed page links to a host that is not on the allow-list
- **THEN** the link is stored in `links` and no request is made to that host
