# social-collection Specification

## Purpose

Collect the public posts of a social platform channel (Telegram `https://t.me/s/<handle>` first, ADR 0103) through the same fetch path as web pages: one document per post, a trusted author from the source URL, bounded paging, and a registry of collectors by host so another platform is one module and one registration.

## Requirements

### Requirement: Accept only a public channel URL
A Telegram source SHALL have a URL of the form `https://t.me/s/<handle>` with `<handle>` of 5 to 32 letters, digits or underscores. The collector SHALL refuse any other URL on a Telegram source with the job error reason `invalid_request`, before any request is made. Every request SHALL pass the same guards, robots check, per-domain rate limit and fetch layer as a web page; the host allow-list is the hosts of the collectable sources, so no setting needs to name `t.me`.

#### Scenario: Valid channel URL
- **WHEN** a run starts for a source with URL `https://t.me/s/SubeTradingPL`
- **THEN** the channel page is requested through the fetch layer

#### Scenario: Wrong URL form
- **WHEN** a run starts for a Telegram source whose URL is `https://t.me/SubeTradingPL` or `https://t.me/s/ab`
- **THEN** no request is made and a job error with reason `invalid_request` is recorded

#### Scenario: Robots refusal
- **WHEN** `robots.txt` of the host refuses the path
- **THEN** no page is requested, no document is emitted and the refusal is not recorded as a block

### Requirement: One document per post
The collector SHALL emit one document per post that has text, with `url` the post permalink, `text` without markup, `published_at` in UTC ISO-8601, `platform` and `source_kind` from the source row, `title` and `lang` null and `canonical_url` equal to `url`. `scrape_meta` SHALL add `message_id`, `views` (integer or null) and `network` (`telegram`). The stored raw HTML SHALL be that post's markup only.

#### Scenario: Text post
- **WHEN** a channel page contains a post with id 1999, text `Sygnał: BTC long, zysk do 30%` and time `2026-11-20T09:15:00+00:00`
- **THEN** one document is emitted with url `https://t.me/<handle>/1999`, that text, `published_at` `2026-11-20T09:15:00+00:00` and `scrape_meta.message_id` 1999

#### Scenario: Network marker
- **WHEN** a post is collected
- **THEN** its `scrape_meta.network` is `telegram` while `platform` is `other`

#### Scenario: Post markup is the stored HTML
- **WHEN** a page with 20 posts is collected
- **THEN** each document's raw HTML contains its own post and none of the other 19

#### Scenario: Post with a line break
- **WHEN** a post text contains line breaks and links
- **THEN** the document text keeps the visible words with whitespace collapsed to single spaces and no tags

#### Scenario: Post edited between runs
- **WHEN** the text of a stored post changes before the next run
- **THEN** a second document with a different `content_hash` is stored for the same permalink

#### Scenario: Identical text in two posts
- **WHEN** a channel posts the same text twice, as posts 1998 and 1999
- **THEN** two documents are stored, one per permalink, because the identity of a social document includes its canonical URL, which is its permalink (`document-ingest`, "Deduplicate by content hash")

#### Scenario: Same post collected again
- **WHEN** post 1999 is collected in two runs with unchanged text
- **THEN** one document exists for it

### Requirement: Posts without text are skipped
A post that has no text (an image, video or sticker with no caption) SHALL NOT produce a document and SHALL NOT be a job error. The run SHALL log the count of skipped posts.

#### Scenario: Image-only post
- **WHEN** a channel page contains a post with a photo and no text
- **THEN** no document is emitted for it, the other posts of the page are collected and the skipped count is logged

#### Scenario: Page of image-only posts
- **WHEN** every post on the page has no text
- **THEN** the run ends without a document and without a job error

### Requirement: Author comes from the channel header
Every document of a channel SHALL carry `author`: `name` the channel title, `handle` the username with a leading `@`, `profile_url` `https://t.me/<handle>`, `followers` the subscriber count as an integer or null. `handle` and `profile_url` SHALL come from the source URL, not page text; a post not of this channel SHALL be ignored. The collector SHALL pass it to ingest as the trusted `author` argument, never in the page dict (issue 36). A `K` or `M` suffix SHALL read as thousands or millions.

#### Scenario: Author is a trusted argument
- **WHEN** a post is ingested
- **THEN** the channel header reaches ingest as its `author` argument and the page dict has no `author` key

#### Scenario: Subscribers with a suffix
- **WHEN** the header shows `36.1K subscribers`
- **THEN** `author.followers` is 36100

#### Scenario: Small plain count
- **WHEN** the header shows `387 subscribers`
- **THEN** `author.followers` is 387

#### Scenario: No counter
- **WHEN** the header has no subscriber counter
- **THEN** `author.followers` is null and the documents are still emitted

### Requirement: Paging is bounded and stateless
The collector SHALL read the newest page first and follow the page's link to older posts (`?before=<id>`, 20 posts a page) until it has seen `SOCIAL_MAX_POSTS` posts, with or without text (default 40) or the next page has no older link. It SHALL stop early when every post with text on a page was already stored. It SHALL keep no state between runs: a rerun starts from the newest page again.

#### Scenario: Default cap
- **WHEN** a channel has 500 posts and `SOCIAL_MAX_POSTS` is unset
- **THEN** two pages are requested and at most 40 documents are emitted

#### Scenario: Nothing new
- **WHEN** a run finds that every post on the newest page already exists
- **THEN** no older page is requested

#### Scenario: Short channel
- **WHEN** the newest page has no link to older posts
- **THEN** exactly one page is requested

#### Scenario: Link to older posts that leaves the channel
- **WHEN** the older-posts link of a page points to another host, another channel or a path other than `/s/<handle>?before=<number>`
- **THEN** it is not requested and the run ends after that page

#### Scenario: Each page is a polite request
- **WHEN** a second page is requested in the same run
- **THEN** it waits for the per-domain rate limit and passes the same guards as the first

### Requirement: Channel without a public preview
A request for a channel that has no public preview (the host answers with a redirect to `https://t.me/<handle>`, so the final URL is off the `/s/` path) SHALL end the run with no document and one job error with reason `parse_error` naming "no public preview". The run SHALL NOT retry it.

#### Scenario: Preview disabled
- **WHEN** `https://t.me/s/<handle>` redirects to `https://t.me/<handle>`
- **THEN** one job error with reason `parse_error` is recorded and no further request is made to that channel in this run

### Requirement: Links are pointers, never fetched
Every link in a post (anchor `href` or a bare URL in the text) SHALL be kept in `links` as `{href, text}` in the contract's shape, including `x.com`, `twitter.com`, `youtu.be`, `youtube.com` and other `t.me` links. The collector SHALL NOT request any of them.

#### Scenario: Post that mirrors an X post
- **WHEN** a post contains `https://x.com/example/status/123`
- **THEN** that URL is in the document's `links` and no request is made to `x.com`

#### Scenario: Link to another channel
- **WHEN** a post links to `https://t.me/otherchannel`
- **THEN** it is kept in `links` and the other channel is not collected unless it has its own source row

### Requirement: Failures never produce a document
A blocked response (403, 429, block marker), a timeout, an HTTP error status, or a page with neither a channel header nor any post SHALL end the run with the job error reason defined by `web-collection` for that condition and SHALL NOT emit a document from that page. A page with a channel header and no posts SHALL end the run without a document and without a job error. If a later page of a run fails, the documents of the earlier pages are kept and the failure is recorded once.

#### Scenario: Blocked on the first page
- **WHEN** the first page returns 429
- **THEN** no document is emitted and the run reports the block as `web-collection` defines it

#### Scenario: Blocked on the second page
- **WHEN** page one is collected and page two returns 403
- **THEN** the documents of page one are kept, one job error with reason `blocked` is recorded and no further page is requested

#### Scenario: Page that is not a channel
- **WHEN** the response is 200 HTML with neither header nor posts
- **THEN** a job error with reason `parse_error` is recorded and nothing is emitted

#### Scenario: Empty channel
- **WHEN** the response has the header and no posts
- **THEN** the run ends without a document and without a job error

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

### Requirement: Telegram channels are seeded as sources
This change SHALL provide the Telegram `sources` rows for the demo, written through the seed mechanism of `scraper-orchestration` (idempotent by URL, never overwriting, the dashboard owns later edits). Each row has `platform = other`, a `https://t.me/s/<handle>` URL and a schedule. A broker-promoting channel targets `M1` with `third_party`; a signals or advice channel targets `M3` with `unknown` (registry status is not known to the scraper); a news channel may be a control.

#### Scenario: Seeding twice
- **WHEN** the seed runs twice against the same database
- **THEN** each channel has exactly one `sources` row

#### Scenario: Seeded channels are scheduled and allowed
- **WHEN** the channels are seeded and the scheduler lists sources
- **THEN** each channel with a cron is schedulable, and its host `t.me` is allowed by the URL guard

#### Scenario: Signal channel is an M3 candidate
- **WHEN** the seed rows are read
- **THEN** `crypto_sygnaly` and `SubeTradingPL` have `source_kind = unknown` and `target_modules = [M3]`, and `rarecryptosignals` has `source_kind = third_party` and `target_modules = [M1]`

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

### Requirement: The X flow runs from the home IP
The X flow SHALL read through an account-based library with the cookies of a dedicated account and SHALL NOT read `robots.txt`, draw a run identity, open a fetch-layer session or use the proxy rotation: it runs from the home IP (ADR 0109). It SHALL still pass the URL guard, and the per-domain rate limit SHALL apply once before its first request.

#### Scenario: X run passes the guards and skips robots
- **WHEN** a run starts for an X source
- **THEN** the URL guard runs, the per-domain limiter is waited once, no `robots.txt` request is made and no proxy of the rotation is used

### Requirement: The transcript request uses its own proxy
The YouTube transcript request SHALL use only its own proxy `YT_TRANSCRIPT_PROXY` and no robots check. Every other request of the system keeps the robots rule.

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
