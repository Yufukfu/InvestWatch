# x-collection Specification

## Purpose

Collect the newest public posts of an X account with the cookies of a dedicated account, one document per post, with a trusted author from the source URL, bounded and stopping at the first sign of restriction so that the dedicated account is not put at risk (ADR 0109).

## Requirements

### Requirement: Accept only a public account URL
An X source SHALL have a URL of the form `https://x.com/<handle>` with `<handle>` of 1 to 15 letters, digits or underscores. The collector SHALL refuse any other URL on an X source with the job error reason `invalid_request`, before any request is made.

#### Scenario: Valid account URL
- **WHEN** a run starts for a source with URL `https://x.com/uknf` and platform `x`
- **THEN** the account's posts are requested

#### Scenario: Wrong URL form
- **WHEN** a run starts for an X source whose URL is `https://x.com/uknf/status/123` or `https://x.com/search?q=btc`
- **THEN** no request is made and a job error with reason `invalid_request` is recorded

### Requirement: Cookies come from the environment
The collector SHALL read `X_AUTH_TOKEN` and `X_CT0` from the environment. A missing or empty value SHALL end the run before any request with the job error reason `invalid_request` and the detail "X cookies are not configured".

#### Scenario: Cookies missing
- **WHEN** `X_AUTH_TOKEN` or `X_CT0` is unset or empty and an X source is run
- **THEN** no request is made and one job error with reason `invalid_request` and that detail is recorded

### Requirement: One document per original post
The collector SHALL emit one document per original post or quote that has text, with `url` the permalink `https://x.com/<handle>/status/<id>`, `text` the full text as the platform returns it, `published_at` in UTC ISO-8601 from the creation time, `platform` `x` and `source_kind` from the source row. A repost of another account's post SHALL be skipped and counted.

#### Scenario: Text post
- **WHEN** the account has a post with id 2123819354898731226, text `Z upoważnienia Komisji…` and creation time `Fri Nov 20 16:42:47 +0000 2026`
- **THEN** one document is emitted with url `https://x.com/uknf/status/2123819354898731226`, that text and `published_at` `2026-11-20T16:42:47+00:00`

#### Scenario: Repost of another account
- **WHEN** the timeline contains a repost of another account's post
- **THEN** no document is emitted for it and the skipped count is logged

#### Scenario: Post without text
- **WHEN** a post has only media and no text
- **THEN** no document is emitted and it is not a job error

#### Scenario: Same post collected again
- **WHEN** the same post is collected in two runs with unchanged text
- **THEN** one document exists for it

### Requirement: Post fields and stored html
`title` SHALL be null, `canonical_url` equal to `url`, and `lang` the platform's code when it is two lowercase letters and null otherwise. `scrape_meta.post_id` SHALL hold the post id and `scrape_meta.scraper` SHALL be `api`. `html` SHALL hold the post as JSON restricted to id, text, creation time, language, handle and media count, with no cookie, token or viewer field.

#### Scenario: Language code outside the contract
- **WHEN** the platform returns the language `und` or `qme`
- **THEN** the document's `lang` is null and the document is stored

#### Scenario: Stored html holds no viewer data
- **WHEN** a post is stored
- **THEN** its `html` parses as JSON with only the listed keys

### Requirement: Author comes from the source URL
Every document SHALL carry `author` with `handle` the source URL's handle with a leading `@`, `profile_url` `https://x.com/<handle>`, `name` the display name the platform returns and `followers` its follower count as an integer or null. `handle` and `profile_url` SHALL come from the source URL and never from a post.

#### Scenario: Author is a trusted argument
- **WHEN** a post is ingested
- **THEN** the author reaches ingest as its `author` argument and the page dict has no `author` key

#### Scenario: No follower count or name
- **WHEN** the platform returns no follower count or no display name
- **THEN** `followers` or `name` is null and the documents are still emitted

### Requirement: Bounded run
A run SHALL read at most `SOCIAL_MAX_POSTS` posts (default 40, shared with Telegram, never more than 40) with one adapter timeline call, which the library answers with at most two timeline requests of twenty posts, and SHALL stop at an empty page. The run SHALL make one further account lookup, for the follower count, only after that call returned posts, and a failed lookup without a restriction marker SHALL leave `followers` null instead of failing the run.

#### Scenario: Default cap
- **WHEN** an account has 500 posts and `SOCIAL_MAX_POSTS` is unset
- **THEN** at most 40 documents are emitted and the adapter's timeline call is made once

#### Scenario: Cap below one page
- **WHEN** `SOCIAL_MAX_POSTS` is 15
- **THEN** the timeline call asks for 15 posts and at most 15 documents are emitted

#### Scenario: No posts, no follower lookup
- **WHEN** the timeline call returns no post
- **THEN** no follower lookup is made

### Requirement: Stop at the first restriction
The adapter SHALL report an authentication failure, a challenge, a suspension marker or a rate limit as a restriction, and the run SHALL end at once with the job error reason `blocked`, keep documents already stored and make no further call.

#### Scenario: Account restricted
- **WHEN** the adapter reports a restriction on the timeline call or on the follower lookup
- **THEN** the run ends with reason `blocked`, no further call is made and stored documents stay

#### Scenario: Unknown library error
- **WHEN** the library fails in a way the adapter cannot classify
- **THEN** one job error with reason `http_error` (a network failure), `timeout` or `parse_error` (an unreadable answer) is recorded, according to the mapping, and no document is emitted for that call

### Requirement: An empty timeline is not an error
The library gives no separate signal for an empty not-found answer, so an empty timeline SHALL be logged and SHALL NOT be a job error.

#### Scenario: Empty timeline
- **WHEN** the timeline call returns no post
- **THEN** the run stores nothing, logs it and records no job error

### Requirement: A lost account is not deactivated automatically
Nothing SHALL deactivate the source automatically: the queue's block handling applies and the owner removes the schedule if the account is lost.

#### Scenario: Blocked run leaves the source as it was
- **WHEN** a run ends with reason `blocked`
- **THEN** the source stays active and its schedule is not changed

### Requirement: Malformed posts are skipped, not stored empty
A post without an id or a creation time SHALL be skipped and counted in the log. If every post of a run is skipped for being malformed, the run SHALL record one job error with reason `parse_error`. A document with empty `text` SHALL never be emitted.

#### Scenario: One malformed post
- **WHEN** one post of a page lacks an id
- **THEN** it is skipped with a logged count and the other posts are collected

#### Scenario: Every post malformed
- **WHEN** no post of the page has an id and a creation time
- **THEN** no document is emitted and one job error with reason `parse_error` is recorded

### Requirement: The X account is seeded without a schedule
This change SHALL provide an X `sources` row for `https://x.com/uknf` through the seed mechanism (idempotent by URL, never overwriting), with `platform = x`, `source_kind = unknown`, `target_modules = [M1]` and no `schedule_cron`, so that it runs on a scan request only until the owner adds a cron once the cookies are in `.env`.

#### Scenario: Seeding twice
- **WHEN** the seed runs twice against the same database
- **THEN** the account has exactly one `sources` row, with no schedule

#### Scenario: Not scheduled
- **WHEN** the scheduler lists sources
- **THEN** the X row is not scheduled, and a scan request for it starts a run
