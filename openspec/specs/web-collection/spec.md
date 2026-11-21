# web-collection Specification

## Purpose

Turn an active registered web source into the parsed fields of a `ScrapedDocument` (`.docs/integration-plan.md` §3, `contracts/schemas/scraped-document.schema.json`), or into a recorded job error when the page cannot be trusted. Terms: a *job* is one enqueued unit of work for a source; an *attempt* is one execution of a job by the queue (the queue may make several; the queue itself is `scraper-orchestration`); a *run* is the fetching done by one attempt, and a *session* is the state of one run. In v1 a run fetches exactly one URL per source (plus its redirects and `robots.txt`); crawling further pages is a later change.

## Requirements

### Requirement: Collect active sources only
A source SHALL be collectable only when its record has `active = true` and either `platform = web` or a `platform` that a registered social collector accepts for the host of its URL (`social-collection`). Selection is a pure function over source records (reading them from PostgreSQL and re-checking at job start belong to `scraper-orchestration`). A source with `schedule_cron = null` is manual only: it is never selected for scheduled runs.

#### Scenario: Inactive source is skipped
- **WHEN** a run starts and the source has `active = false`
- **THEN** no request is made to that source's URL

#### Scenario: Non-web source is skipped
- **WHEN** a run starts for an active source with a `platform` other than `web` and no social collector is registered for the host of its URL
- **THEN** no request is made and no job error is recorded for it

#### Scenario: Social source with a collector is selected
- **WHEN** a run starts for an active source with `platform = other` and a collector registered for its host
- **THEN** the source is collectable

#### Scenario: Manual-only source is not scheduled
- **WHEN** the scheduler plans runs and an active web source has `schedule_cron = null`
- **THEN** it is not selected for scheduled runs

### Requirement: Parse a fetched page into contract fields
For a successful fetch the scraper SHALL produce the contract fields `url`, `canonical_url`, `fetched_at` (UTC), `http_status`, `title`, `text`, `links`, `platform`, `source_kind` and `scrape_meta`. `source_kind` SHALL be copied from the `sources` row, never inferred from the page.

#### Scenario: Article page is parsed
- **WHEN** a saved fixture of an article page with `<title>Akcje: ryzyko</title>` and a relative link `/kontakt` is parsed
- **THEN** `title` equals `Akcje: ryzyko`, `text` is non-empty, and `links` contains the absolute URL of `/kontakt`

#### Scenario: Source kind comes from the source row
- **WHEN** a source row has `source_kind = firm_own`
- **THEN** the resulting document has `source_kind = firm_own` regardless of page content

#### Scenario: Saved real page
- **WHEN** the saved fixture of the KNF public warnings page is parsed
- **THEN** `text` is longer than 100000 characters, `title` is non-empty and `canonical_url` is an absolute `https` URL

### Requirement: Derive title, canonical URL and links predictably
`title` SHALL be the trimmed text of `<title>`, falling back to the first `<h1>`, else null. `canonical_url` SHALL be `<link rel="canonical">` resolved against the final URL, else the final URL. `links` SHALL hold only `http` and `https` links resolved to absolute URLs; `mailto:`, `javascript:` and fragment-only links are dropped.

#### Scenario: Title and canonical fallbacks
- **WHEN** a fixture has no `<title>` but an `<h1>`, and no canonical link
- **THEN** `title` is the `<h1>` text and `canonical_url` equals the final URL

#### Scenario: Non-navigational links are dropped
- **WHEN** a page contains `mailto:a@b.pl`, `javascript:void(0)` and `#top`
- **THEN** none of them appears in `links`

### Requirement: Decode and bound the response body
The body SHALL be decoded with the charset from the `Content-Type` header or the `<meta>` declaration, so Polish pages in windows-1250 or ISO-8859-2 keep their letters. A response whose `Content-Type` is not HTML is a `parse_error`. A body larger than the configured size cap (default 5 MiB) is a `parse_error`. The body is streamed to a temporary file, never held whole in memory, and the cap is checked on the transferred size; the request timeout bounds the transfer.

#### Scenario: Polish charset
- **WHEN** a fixture is served as windows-1250 with the word `żółć`
- **THEN** the stored `text` contains `żółć`

#### Scenario: Non-HTML response
- **WHEN** a response is `application/pdf`
- **THEN** a job error with reason `parse_error` is recorded and no document is produced

#### Scenario: Oversized body
- **WHEN** a stub server answers with a body larger than the cap
- **THEN** a job error with reason `parse_error` is recorded, no document is produced and the temporary file is removed

### Requirement: Add a site without changing the engine
Page parsing SHALL go through a registry keyed by host. A site module registers a parser for its host; a host with no module uses the generic parser.

#### Scenario: Host with its own parser
- **WHEN** a parser is registered for `example.pl` and a page from `example.pl` is parsed
- **THEN** the registered parser is used and the generic one is not

#### Scenario: Host without a parser
- **WHEN** a page from a host with no registered parser is parsed
- **THEN** the generic parser is used

### Requirement: Never emit a document from a failed or blocked fetch
The scraper SHALL record a job error with a reason from the closed set below instead of a document when the fetch is blocked, fails, or yields no text. Block signals SHALL include HTTP 403 and 429, captcha markers and a zero-length response body. A non-block HTTP error status (for example 404 or 5xx) is `http_error`; a body with no extractable text is `empty_text`; markup the parser cannot process is `parse_error`.

#### Scenario: Blocked response
- **WHEN** a source responds with HTTP 403, or HTTP 200 with a captcha page
- **THEN** a job error with reason `blocked` is recorded and no document is produced

#### Scenario: Timeout
- **WHEN** a single request exceeds its timeout
- **THEN** the fetch reports `timeout`

#### Scenario: HTTP error status
- **WHEN** a source responds with HTTP 404 or 500
- **THEN** the fetch reports `http_error` and no document is produced

#### Scenario: Malformed markup
- **WHEN** the parser cannot process the fetched markup
- **THEN** a job error with reason `parse_error` is recorded and no document is produced

#### Scenario: Page with no extractable text
- **WHEN** parsing a fetched page yields empty `text`
- **THEN** a job error with reason `empty_text` is recorded and no document is produced

### Requirement: Fetch makes one attempt
`fetch()` SHALL make one attempt per request and never retry; retries belong to the job queue (`scraper-orchestration`), and a job error is recorded once, for the final outcome.

#### Scenario: No retry inside fetch
- **WHEN** a stub server answers 503 on every call
- **THEN** `fetch()` makes exactly one request and reports `http_error`

### Requirement: Use one closed set of job error reasons
Every job error SHALL carry exactly one reason from `blocked`, `blocked_target`, `timeout`, `http_error`, `parse_error`, `empty_text`, `schema_invalid`, `storage_error`, `publish_failed`, `invalid_request` (a scan request or source configuration that cannot be run), `render_failed` (a failed render step that did not end in a block, a refused target or a storage error; defined by `page-rendering`). The condition for each is defined in the requirement that names it.

#### Scenario: Only listed reasons can be recorded
- **WHEN** code attempts to record a job error with the reason `oops`
- **THEN** the attempt is rejected and nothing is stored under that reason

#### Scenario: Render failure has its own reason
- **WHEN** the renderer is unreachable during a run
- **THEN** the job error is recorded with the reason `render_failed`, which the closed set accepts and which is stored as text in `job_errors.reason` without a database migration

### Requirement: Start a fresh session for every run
A session is one run (one attempt of one source): it covers the page request, its redirect hops and the `robots.txt` request. Every attempt, including a queue retry, SHALL start with an empty cookie jar and a newly drawn identity, and SHALL never reuse another run's or another source's session state.

#### Scenario: No state carried between runs
- **WHEN** a stub server sets a cookie during one run and the same source is run again
- **THEN** the second run sends no cookie

#### Scenario: Identity drawn per run
- **WHEN** a run starts
- **THEN** an identity is drawn from the identity table for that run only

#### Scenario: Second run gets a fresh session
- **WHEN** a second run starts for the same source after the first ended in a timeout
- **THEN** the second run sends no cookie from the first and draws its own identity

### Requirement: Send headers in the order of the user agent's browser
An identity is a user agent, an ordered header set and a TLS profile of one browser family, taken from the identity table, which lists every header to send (headers not listed are appended by the client in its own order) and carries only current browser versions. The scraper SHALL send the profile's headers with the profile's values in the profile's order on every request of the session, and a custom header SHALL NOT reorder or replace profile headers.

#### Scenario: Header order on the wire
- **WHEN** a request is made with the Chrome identity against a raw-socket stub that records the header lines
- **THEN** the recorded header names appear in exactly the order defined for that profile, and `User-Agent` is the profile's

#### Scenario: Pairing in the table
- **WHEN** the identity table is loaded
- **THEN** every user agent is paired with a TLS profile and header order of its own browser family, and a mismatched entry is rejected at load

### Requirement: Use a different proxy for each request
With `PROXY_ROTATION=per_request` (default) the scraper SHALL pick the proxy for every request, redirect hops and `robots.txt` included, from `PROXY_LIST`, and SHALL NOT use the same proxy as the previous request while the list has more than one entry. `PROXY_ROTATION=per_session` fixes one proxy for the session. With an empty `PROXY_LIST` requests are made directly. `scrape_meta.proxy` SHALL hold the identifier of the proxy that served the document request, or null.

#### Scenario: Consecutive requests use different proxies
- **WHEN** a run makes three requests and `PROXY_LIST` has three entries
- **THEN** no two consecutive requests used the same proxy

#### Scenario: Single proxy
- **WHEN** `PROXY_LIST` has one entry
- **THEN** every request uses it

#### Scenario: No proxy configured
- **WHEN** `PROXY_LIST` is empty
- **THEN** requests are made directly and `scrape_meta.proxy` is null

#### Scenario: Random start
- **WHEN** two runs start with the same three-entry `PROXY_LIST`
- **THEN** the first proxy is drawn at random, not always the first entry

#### Scenario: Proxy authentication failure
- **WHEN** a proxy answers 407
- **THEN** that proxy is skipped for `PROXY_COOLDOWN_SECONDS` (default 90) and the request is made through another proxy

#### Scenario: Every proxy cooling down
- **WHEN** every proxy in the list is cooling down
- **THEN** the run reports a deferral until the earliest cooldown ends, makes no request and records no job error

#### Scenario: Per-session mode
- **WHEN** `PROXY_ROTATION=per_session` and a run makes three requests
- **THEN** all three use the same proxy

### Requirement: A block ends the run
A block signal SHALL end the run with `blocked`, discard the session, and not be retried by the queue. The next run draws a new identity. A `robots.txt` refusal is not a block signal.

#### Scenario: Block ends the run
- **WHEN** a response is a block signal
- **THEN** the run records `blocked`, makes no further request, and the session's cookies are discarded

#### Scenario: robots.txt refusal is not a block
- **WHEN** a run is refused by `robots.txt`
- **THEN** the run records `blocked` and no identity is marked as blocked

### Requirement: Be polite to sources
The scraper SHALL honour `robots.txt` and apply a per-domain rate limit that is shared by all workers. An answer of 401, 403, 404 or 410 for `robots.txt` itself means no restrictions (RFC 9309: unavailable); a 429, 5xx or timeout means the path is treated as disallowed for this run. A `robots.txt` answer is never a block signal.

#### Scenario: Disallowed by robots.txt
- **WHEN** `robots.txt` of a source's domain disallows the target path
- **THEN** the page is not fetched and a job error with reason `blocked` is recorded

#### Scenario: robots.txt server error
- **WHEN** fetching `robots.txt` returns HTTP 503 or times out
- **THEN** the page is not fetched and a job error with reason `blocked` is recorded

#### Scenario: robots.txt missing or forbidden
- **WHEN** fetching `robots.txt` returns HTTP 404 or 403
- **THEN** the page is fetched and no identity is penalised

#### Scenario: Rate limit shared across workers
- **WHEN** two workers have a request for the same domain and the limit is one request per 5 seconds
- **THEN** the two requests start at least 5 seconds apart

### Requirement: Honour Retry-After
The scraper SHALL read `Retry-After` as seconds or as an HTTP-date, cap it at a configurable maximum (default 300 s) and defer the whole domain for all workers until the wait has passed. The deferral state is held in Redis. A run that meets an active deferral does not fetch and reports a deferral until the time it ends; this is not a failure (the queue requeues it, see `scraper-orchestration`).

#### Scenario: Retry-After is honoured
- **WHEN** a source answers 429 with `Retry-After: 30`
- **THEN** no worker starts a request to that domain earlier than 30 seconds later, and the 429 run records `blocked`

#### Scenario: Retry-After is capped
- **WHEN** a source answers 429 with `Retry-After: 86400` and the cap is 300 s
- **THEN** the domain is deferred for 300 seconds

#### Scenario: Retry-After as a date
- **WHEN** a source answers 503 with `Retry-After` set to an HTTP-date 20 seconds ahead
- **THEN** the domain is deferred until that time

### Requirement: Pause a domain that keeps failing
After a configurable number of consecutive failure outcomes recorded for a domain (default 5; the queue records one outcome per job, never per attempt), the scraper SHALL pause the domain for a cooldown (default 10 minutes) for all workers; during the pause a run reports a deferral until it ends, and a recorded success resets the count.

#### Scenario: Domain paused
- **WHEN** 5 failure outcomes are recorded for a domain in a row
- **THEN** the next run for it reports a deferral and does not fetch until the cooldown has passed

#### Scenario: Success resets the count
- **WHEN** a success outcome is recorded after 4 failures
- **THEN** the failure count is zero

### Requirement: Fetch only http(s) URLs and allow-listed redirect hosts
The scraper SHALL fetch only `http` and `https` URLs and SHALL follow redirects itself, one hop at a time. Hosts reached by a redirect hop, or taken from scraped content, SHALL be on the allow-list: the hosts of active `sources` rows plus configured extras, where `www.` and the bare host count as the same host. The source URL itself is checked for scheme and address only, since it is on the list by construction. A refusal records a job error with reason `blocked_target` and makes no request.

#### Scenario: URL from scraped content on a foreign host
- **WHEN** the guard is asked whether a URL taken from scraped content on a non-allow-listed host may be fetched
- **THEN** it refuses with `blocked_target`, and the link itself stays in `links` (v1 fetches no scraped link; the guard is tested directly)

#### Scenario: Redirect to a host outside the allow-list
- **WHEN** a source redirects to a host that is not on the allow-list
- **THEN** the redirect is not followed and a job error with reason `blocked_target` is recorded

#### Scenario: Apex to www redirect
- **WHEN** `example.pl` redirects to `www.example.pl` and only `example.pl` is a source
- **THEN** the redirect is followed

#### Scenario: Non-http scheme
- **WHEN** a source URL is `file:///etc/passwd` or `ftp://host/x`
- **THEN** no request is made and a job error with reason `blocked_target` is recorded

### Requirement: Refuse internal addresses and connect to the checked one
For every request the scraper SHALL resolve the host itself, refuse a loopback, private, link-local, unique-local, unspecified or multicast result (IPv4, IPv6 and IPv4-mapped forms), refuse bare compose service names and hosts in `COMPOSE_INTERNAL_HOSTS`, and connect to the address it checked. A refusal records `blocked_target`. Behind a proxy the proxy resolves the host itself; that residual risk is accepted (`design.md`).

#### Scenario: Source URL resolving to an internal address
- **WHEN** a source URL (for example one edited from the dashboard) resolves to `127.0.0.1`, `::1`, `10.0.0.5`, `169.254.169.254`, `::ffff:127.0.0.1` or `0.0.0.0`
- **THEN** no request is made and a job error with reason `blocked_target` is recorded

#### Scenario: DNS answer changes between check and connect
- **WHEN** a host resolves to a public address at the check and the connection would resolve it to `127.0.0.1`
- **THEN** the connection uses the checked address, never a second resolution

### Requirement: Fetch only allowed ports
The scraper SHALL request only ports listed in `ALLOWED_PORTS` (default `80,443`), for the source URL, every redirect hop and every URL taken from scraped content. A URL with no explicit port uses its scheme's default (80 for `http`, 443 for `https`). The check applies behind a proxy too, since the port is part of the URL. A refusal records `blocked_target` and makes no request.

#### Scenario: Non-web port
- **WHEN** a source URL, a redirect `Location` or a scraped link names `https://example.pl:6379/`
- **THEN** no request is made and a job error with reason `blocked_target` is recorded

#### Scenario: Default and explicit web ports
- **WHEN** a URL is `http://example.pl/`, `https://example.pl/` or `https://example.pl:443/`
- **THEN** the port check passes

#### Scenario: Configured extra port
- **WHEN** `ALLOWED_PORTS` is `80,443,8443` and a URL names `https://example.pl:8443/`
- **THEN** the port check passes

### Requirement: Treat scraped content as untrusted
The scraper SHALL store scraped text verbatim and SHALL NOT template it.

#### Scenario: Markup-like text is stored unchanged
- **WHEN** a page contains the text `{{ 7*7 }}`
- **THEN** the stored `text` contains `{{ 7*7 }}` and not `49`

### Requirement: Never record credentials
The scraper SHALL NOT write a proxy URL with credentials, or any other secret, to logs, job errors or documents. `scrape_meta.proxy` SHALL hold an identifier, never a URL.

#### Scenario: Failure through an authenticated proxy
- **WHEN** a request through a proxy `http://user:secret@host:8080` fails
- **THEN** the job error and the log line contain a proxy identifier only, and neither contains `secret`
