## MODIFIED Requirements

### Requirement: Social collection uses the same fetch path as web pages
The Telegram collector and the YouTube collector's channel and watch pages SHALL be requested through the same fetch layer, robots check, per-domain rate limit and URL guards as a web page, with no HTTP client, proxy handling or header logic of its own. One identity SHALL be drawn per run and used for every page of it, and a proxy SHALL be chosen per request with the same rotation and cooldown as for web sources (this meets the brief's user-agent and proxy rotation).

#### Scenario: Identity and proxy come from the shared layer
- **WHEN** a run collects two pages of a Telegram channel with proxies configured
- **THEN** both requests carry the identity drawn for that run, each request is made through a proxy picked by the shared rotation, and no request is made outside the fetch layer

#### Scenario: Paging respects the domain limit
- **WHEN** the collector requests the second page right after the first
- **THEN** the per-domain interval of the rate limiter elapses between the two request starts

#### Scenario: Blocked page ends the run
- **WHEN** a page of the channel is answered as a block
- **THEN** the run ends, documents already stored stay, and no further page is requested

#### Scenario: Web, Telegram and YouTube pages keep the robots rule
- **WHEN** a web, Telegram or YouTube source is run after this change
- **THEN** its `robots.txt` is read and honoured as before

### Requirement: Register a collector per host
Social collectors SHALL be registered by host in a registry beside the page-parser registry. A registration SHALL carry the one `platform` value its sources have and the URL form a source of that platform must have, and SHALL name either a page parser (Telegram) or a dedicated flow (X, YouTube) that `run_source` dispatches by `source.platform`. A host with no registration SHALL NOT be collected by the social path.

#### Scenario: Host with a collector
- **WHEN** a collector is registered for `t.me` and a source on `t.me` is run
- **THEN** the registered collector is used and the generic page parser is not

#### Scenario: Duplicate registration
- **WHEN** a second collector is registered for the same host
- **THEN** the registration is refused

#### Scenario: Dedicated flow
- **WHEN** a source with platform `x` and a valid `https://x.com/<handle>` URL is run
- **THEN** the X flow runs and the Telegram page path does not

## ADDED Requirements

### Requirement: Dedicated flows outside the shared fetch path
The X flow SHALL read through an account-based library with the cookies of a dedicated account and SHALL NOT read `robots.txt`, draw a run identity, open a fetch-layer session or use the proxy rotation: it runs from the home IP (ADR 0109). It SHALL still pass the URL guard, and the per-domain rate limit SHALL apply once before its first request. The YouTube transcript request SHALL use only its own proxy `YT_TRANSCRIPT_PROXY` and no robots check. Every other request of the system keeps the robots rule.

#### Scenario: X run passes the guards and skips robots
- **WHEN** a run starts for an X source
- **THEN** the URL guard runs, the per-domain limiter is waited once, no `robots.txt` request is made and no proxy of the rotation is used

#### Scenario: Transcript uses only its own proxy
- **WHEN** a transcript is requested while `PROXY_LIST` is also set
- **THEN** the request goes through `YT_TRANSCRIPT_PROXY` and never through a proxy of the rotation

### Requirement: Secrets never leave the process
No cookie or proxy URL (`X_AUTH_TOKEN`, `X_CT0`, `YT_TRANSCRIPT_PROXY`, their values, the proxy host and its credentials) SHALL appear in a log line, job error, exception text, traceback, document, `scrape_meta`, event or fixture. Each adapter SHALL catch every exception of its library at its boundary, map it to a `Reason`, and raise without the original as its cause.

#### Scenario: Library error carries the secrets
- **WHEN** a library raises an exception whose message and cause contain the cookie value and the proxy host
- **THEN** the recorded job error, every log line and the traceback of the failure contain neither

#### Scenario: Unknown library exception
- **WHEN** a library raises an exception type the adapter does not know
- **THEN** it is mapped to a job error with a reason from the closed set and the job is not failed as a crash

### Requirement: Committed fixtures hold no credentials or tokens
Fixtures saved from real X or YouTube responses SHALL have cookies, `visitorData`, session tokens and viewer fields removed before they are committed.

#### Scenario: Secret scan of fixtures
- **WHEN** the test suite scans `scraper/tests/fixtures/`
- **THEN** it fails if any file contains `auth_token`, `ct0` followed by a value, a `cookie:` header, `visitorData`, or a `user:password@` URL
