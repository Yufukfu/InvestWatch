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
The scraper SHALL record a job error with a reason (`blocked`, `timeout`, `http_error`, `parse_error`, `empty_text`) instead of a document when the fetch is blocked, fails, or yields no text. Block signals SHALL include HTTP 403 and 429, captcha markers and a zero-length response body. A non-block HTTP error status (for example 404 or 5xx) is `http_error`. A response that has a body but no extractable text is `empty_text`, and markup the parser cannot process is `parse_error`.

#### Scenario: Blocked response
- **WHEN** a source responds with HTTP 403, or HTTP 200 with a captcha page
- **THEN** a job error with reason `blocked` is recorded and no document is produced

#### Scenario: Timeout
- **WHEN** a request exceeds its timeout after the configured retry cap
- **THEN** a job error with reason `timeout` is recorded and no document is produced

#### Scenario: HTTP error status
- **WHEN** a source responds with HTTP 404 or 500
- **THEN** a job error with reason `http_error` is recorded and no document is produced

#### Scenario: Malformed markup
- **WHEN** the parser cannot process the fetched markup
- **THEN** a job error with reason `parse_error` is recorded and no document is produced

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

### Requirement: Keep one identity per session
The scraper SHALL choose proxy, user agent, header set and TLS profile together, SHALL keep them fixed for the lifetime of a session's cookies, and SHALL rotate the whole identity, never a part of it, on a block signal.

#### Scenario: Identity stays fixed within a session
- **WHEN** several requests are made in one session
- **THEN** every request carries the same user agent, header set and TLS profile, and a user agent is never paired with a TLS profile of another browser family

#### Scenario: Block rotates the whole identity
- **WHEN** a response is a block signal
- **THEN** the next session starts with a different complete identity and discards the old session's cookies

### Requirement: Fetch only allow-listed, public hosts
The scraper SHALL fetch only hosts on the allow-list, which is the hosts of active `sources` rows plus hosts added in configuration. This applies to the source URL, to every redirect hop, and to any URL taken from scraped content. The scraper SHALL also refuse any host that resolves to a private, loopback, link-local or compose-internal address, and SHALL record a job error with reason `blocked_target` instead of fetching it.

#### Scenario: Link to a non-allow-listed host is not followed
- **WHEN** a parsed page links to a host that is not on the allow-list
- **THEN** the link is stored in `links` and no request is made to that host

#### Scenario: Redirect to a host outside the allow-list
- **WHEN** a source redirects to a host that is not on the allow-list
- **THEN** the redirect is not followed and a job error with reason `blocked_target` is recorded

#### Scenario: Source URL resolving to an internal address
- **WHEN** a source URL (for example one edited from the dashboard) resolves to a loopback, link-local or compose-internal address
- **THEN** no request is made and a job error with reason `blocked_target` is recorded

### Requirement: Treat scraped content as untrusted
The scraper SHALL store scraped text verbatim and SHALL NOT execute or template it.

#### Scenario: Markup-like text is stored unchanged
- **WHEN** a page contains text such as `{{ 7*7 }}` or `<script>alert(1)</script>`
- **THEN** the stored `text` contains it verbatim and nothing is evaluated

### Requirement: Never record credentials
The scraper SHALL NOT write a proxy URL with credentials, or any other secret, to logs, job errors or documents. `scrape_meta.proxy` SHALL hold an identifier, never a URL.

#### Scenario: Failure through an authenticated proxy
- **WHEN** a request through a proxy `http://user:secret@host:8080` fails
- **THEN** the job error and the log line contain a proxy identifier only, and neither contains `secret`
