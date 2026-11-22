## Purpose

Collect the newest public posts of an X account with the cookies of a dedicated account, one document per post, with a trusted author from the source URL, bounded and paced so that the dedicated account is not put at risk (ADR 0109).

## ADDED Requirements

### Requirement: Accept only a public account URL
An X source SHALL have a URL of the form `https://x.com/<handle>` with `<handle>` of 1 to 15 letters, digits or underscores. The collector SHALL refuse any other URL on an X source with the job error reason `invalid_request`, before any request is made.

#### Scenario: Valid account URL
- **WHEN** a run starts for a source with URL `https://x.com/uknf` and platform `x`
- **THEN** the account's posts are requested

#### Scenario: Wrong URL form
- **WHEN** a run starts for an X source whose URL is `https://x.com/uknf/status/123` or `https://x.com/search?q=btc`
- **THEN** no request is made and a job error with reason `invalid_request` is recorded

### Requirement: Cookies come from the environment only
The collector SHALL read the account cookies `X_AUTH_TOKEN` and `X_CT0` from the environment. They SHALL NOT appear in any log line, job error, document, `scrape_meta`, event or exception message. A missing cookie SHALL end the run before any request with the job error reason `invalid_request` and the detail "X cookies are not configured".

#### Scenario: Cookies missing
- **WHEN** `X_AUTH_TOKEN` or `X_CT0` is unset or empty and an X source is run
- **THEN** no request is made and one job error with reason `invalid_request` is recorded

#### Scenario: Cookies never leave the process
- **WHEN** a run fails with any error while the cookies are set
- **THEN** no log line, job error or exception text contains either cookie value

### Requirement: One document per post
The collector SHALL emit one document per original post and per quote that has text, with `url` the permalink `https://x.com/<handle>/status/<id>`, `text` the full text as the platform returns it, `published_at` in UTC ISO-8601 from the post's creation time, `platform` `x`, `source_kind` from the source row, `title` null, `lang` the platform's language code when it gives one, and `canonical_url` equal to `url`. `scrape_meta.post_id` SHALL hold the post id. A repost of another account's post SHALL be skipped (the text belongs to someone else) and counted.

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

### Requirement: Author comes from the source URL
Every document SHALL carry `author` with `handle` the source URL's handle with a leading `@`, `profile_url` `https://x.com/<handle>`, `name` the display name the platform returns for that account and `followers` its follower count as an integer or null. `handle` and `profile_url` SHALL come from the source URL and never from the post.

#### Scenario: Author is a trusted argument
- **WHEN** a post is ingested
- **THEN** the author reaches ingest as its `author` argument and the page dict has no `author` key

#### Scenario: No follower count
- **WHEN** the platform returns no follower count
- **THEN** `author.followers` is null and the documents are still emitted

### Requirement: Bounded and paced
A run SHALL request at most `SOCIAL_MAX_POSTS` posts (default 40, shared with Telegram) in at most two timeline requests, and SHALL NOT request a second timeline page when the first brought no new post. The run SHALL stop at the first sign that the dedicated account is restricted: an authentication failure, a challenge, a suspension, an empty not-found answer on an endpoint that answered before, or a rate limit.

#### Scenario: Default cap
- **WHEN** an account has 500 posts and `SOCIAL_MAX_POSTS` is unset
- **THEN** at most 40 documents are emitted and at most two timeline requests are made

#### Scenario: Nothing new
- **WHEN** every post of the first page already exists
- **THEN** no second page is requested

#### Scenario: Account restricted
- **WHEN** the platform answers a run with an authentication failure, a challenge, a suspension marker or HTTP 429
- **THEN** the run ends with the job error reason `blocked`, documents already stored stay, no retry is made in the same run and the queue's block handling applies

### Requirement: Failures never produce a document
A failure (unreadable response, library error, schema mismatch of a post) SHALL end the run or skip the post with a job error from the closed reason set (`parse_error`, `http_error`, `blocked`, `timeout`) and SHALL NOT emit a document with empty `text`.

#### Scenario: Library error
- **WHEN** the library raises while reading the timeline
- **THEN** one job error with reason `parse_error` or `http_error` is recorded and no document is emitted for that request

#### Scenario: Malformed post
- **WHEN** one post of a page lacks an id or a creation time
- **THEN** that post is skipped with a logged count and the other posts are collected

### Requirement: X accounts are seeded inactive
This change SHALL provide an X `sources` row for `https://x.com/uknf` through the seed mechanism (idempotent by URL, never overwriting), with `platform = x`, `active = false`, a schedule and the module targets of the source's kind, so that the owner turns it on once the cookies are in `.env`.

#### Scenario: Seeding twice
- **WHEN** the seed runs twice against the same database
- **THEN** the account has exactly one `sources` row and it is inactive

#### Scenario: Inactive source is not scheduled
- **WHEN** the scheduler lists sources and the row is inactive
- **THEN** it is not scheduled
