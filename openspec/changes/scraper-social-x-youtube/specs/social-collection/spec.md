## MODIFIED Requirements

### Requirement: Social collection uses the same fetch path as web pages
The Telegram collector and the YouTube collector's page requests SHALL go through the same fetch layer, robots check, per-domain rate limit and URL guards as a web page, with no HTTP client, proxy handling or header logic of its own. One identity SHALL be drawn per run and used for every page of it, and a proxy SHALL be chosen per request with the same rotation and cooldown as for web sources (this meets the brief's user-agent and proxy rotation). The X collector is the one exception: it reads through an account-based library with the cookies of a dedicated account and does not read `robots.txt` (ADR 0109); it SHALL still pass the URL guard and the per-domain rate limit before its first request. The YouTube transcript request is the other exception: it uses its own dedicated proxy and no robots check (ADR 0109).

#### Scenario: Identity and proxy come from the shared layer
- **WHEN** a run collects two pages of a Telegram channel with proxies configured
- **THEN** both requests carry the identity drawn for that run, each request is made through a proxy picked by the shared rotation, and no request is made outside the fetch layer

#### Scenario: Paging respects the domain limit
- **WHEN** the collector requests the second page right after the first
- **THEN** the per-domain interval of the rate limiter elapses between the two request starts

#### Scenario: Blocked page ends the run
- **WHEN** a page of the channel is answered as a block
- **THEN** the run ends, documents already stored stay, and no further page is requested

#### Scenario: X run still passes the guards
- **WHEN** a run starts for an X source
- **THEN** the URL guard and the per-domain rate limit apply before the first request, and no `robots.txt` request is made

#### Scenario: Web and Telegram keep the robots rule
- **WHEN** a web or Telegram source is run after this change
- **THEN** its `robots.txt` is read and honoured as before

### Requirement: Register a collector per host
Social collectors SHALL be registered by host in a registry beside the page-parser registry, each with the one `platform` value its sources carry (`other` for Telegram, `x` for X, `youtube` for YouTube) and the URL form a source of that platform must have. A host with no collector SHALL NOT be collected by the social path.

#### Scenario: Host with a collector
- **WHEN** a collector is registered for `t.me` and a source on `t.me` is run
- **THEN** the registered collector is used and the generic page parser is not

#### Scenario: Duplicate registration
- **WHEN** a second collector is registered for the same host
- **THEN** the registration is refused

#### Scenario: Platform must match the host
- **WHEN** a source with platform `x` has the URL of a YouTube channel
- **THEN** no request is made and a job error with reason `invalid_request` is recorded
