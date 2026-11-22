## Purpose

Collect the newest videos of a public YouTube channel, one document per video with its title, description and, when obtainable, its transcript, so that investment-scam pitches in video content reach the analysis (ADR 0109).

## ADDED Requirements

### Requirement: Accept only a public channel URL
A YouTube source SHALL have a URL of the form `https://www.youtube.com/@<handle>` with `<handle>` of 3 to 30 letters, digits, dots, hyphens or underscores. The collector SHALL refuse any other URL on a YouTube source with the job error reason `invalid_request`, before any request is made.

#### Scenario: Valid channel URL
- **WHEN** a run starts for a source with URL `https://www.youtube.com/@UKNFpolska` and platform `youtube`
- **THEN** the channel's video list is requested

#### Scenario: Wrong URL form
- **WHEN** a run starts for a YouTube source whose URL is `https://www.youtube.com/watch?v=JLShF0trXZI` or `https://www.youtube.com/results?search_query=btc`
- **THEN** no request is made and a job error with reason `invalid_request` is recorded

### Requirement: Newest videos, bounded
A run SHALL read the channel's video list once, take the newest `YOUTUBE_MAX_VIDEOS` videos (default 10), skip videos that already have a stored document, and request one watch page per remaining video through the shared fetch layer, one at a time. The list page SHALL be requested through the shared fetch layer too; when the list cannot be read there (for example a consent redirect to another host), the run SHALL end with the job error reason `parse_error` naming "no readable video list".

#### Scenario: Default cap
- **WHEN** a channel has 200 videos and `YOUTUBE_MAX_VIDEOS` is unset
- **THEN** one list request and at most 10 watch-page requests are made

#### Scenario: Nothing new
- **WHEN** every listed video already has a stored document
- **THEN** no watch page is requested

#### Scenario: List behind a consent page
- **WHEN** the channel page answers with a redirect to `consent.youtube.com`
- **THEN** no document is emitted and one job error with reason `parse_error` and the detail "no readable video list" is recorded

### Requirement: One document per video
The collector SHALL emit one document per video that is playable, with `url` `https://www.youtube.com/watch?v=<id>`, `platform` `youtube`, `source_kind` from the source row, `title` the video title, `published_at` the publish date in UTC ISO-8601, `lang` null, `canonical_url` equal to `url`, and `text` the title, the description and the transcript (when there is one) joined by blank lines, with the title first. `scrape_meta.video_id` SHALL hold the video id and `scrape_meta.transcript` SHALL be `caption`, `none` or `failed`.

#### Scenario: Video with transcript
- **WHEN** a video has the title `Film jubileuszowy…`, a description and a transcript
- **THEN** one document is emitted whose text starts with the title, followed by the description and the transcript, and `scrape_meta.transcript` is `caption`

#### Scenario: Video without caption track
- **WHEN** a video has no caption track
- **THEN** the document contains the title and the description and `scrape_meta.transcript` is `none`

#### Scenario: Unplayable video
- **WHEN** a watch page reports the video as unavailable, private or age-restricted
- **THEN** no document is emitted for it, the count is logged and it is not a job error

#### Scenario: Same video collected again
- **WHEN** the same video is collected in two runs with unchanged text
- **THEN** one document exists for it

### Requirement: Author comes from the source URL
Every document SHALL carry `author` with `handle` the source URL's handle with a leading `@`, `profile_url` `https://www.youtube.com/@<handle>`, `name` the channel name from the watch page's own fields and `followers` null. `handle` and `profile_url` SHALL come from the source URL and never from the video's text.

#### Scenario: Author is a trusted argument
- **WHEN** a video is ingested
- **THEN** the author reaches ingest as its `author` argument and the page dict has no `author` key

#### Scenario: Video of another channel in the list
- **WHEN** a watch page's channel differs from the source's channel
- **THEN** that video is skipped with a logged count

### Requirement: Transcript through a dedicated proxy
The collector SHALL request the transcript of a video through the caption library with the proxy `YT_TRANSCRIPT_PROXY` (an HTTP proxy URL, env only, never logged), preferring the original-language track and then any available track. A run SHALL request at most one transcript per video and SHALL stop requesting transcripts for the rest of the run after the first block or IP refusal. A missing `YT_TRANSCRIPT_PROXY` SHALL skip transcripts entirely (not a job error): `scrape_meta.transcript` is `none` and the run logs that transcripts are off.

#### Scenario: Proxy configured
- **WHEN** `YT_TRANSCRIPT_PROXY` is set and a video has a Polish caption track
- **THEN** the transcript is requested once through that proxy and its text is part of the document

#### Scenario: Proxy not configured
- **WHEN** `YT_TRANSCRIPT_PROXY` is unset
- **THEN** no transcript request is made and the documents carry title and description only

#### Scenario: Block on the first transcript
- **WHEN** the first transcript request is refused with an IP block or a rate limit
- **THEN** no further transcript is requested in the run, that video's `scrape_meta.transcript` is `failed` and the other videos are still collected without a transcript

#### Scenario: Proxy credentials stay secret
- **WHEN** a transcript request fails with any error
- **THEN** no log line, job error or exception text contains the proxy URL, host or credentials

### Requirement: Failures never produce a document
A failure (a watch page that cannot be read, a missing player response) SHALL end the run or skip the video with a job error from the closed reason set and SHALL NOT emit a document with empty `text`. A block on the shared fetch layer ends the run and is not retried.

#### Scenario: Unreadable watch page
- **WHEN** a watch page has no readable player response
- **THEN** that video is skipped with a job error `parse_error` and the run goes on with the next video

#### Scenario: Block on a watch page
- **WHEN** a watch page is answered as a block
- **THEN** the run ends, documents already stored stay and no further watch page is requested

### Requirement: YouTube channels are seeded inactive
This change SHALL provide a YouTube `sources` row for `https://www.youtube.com/@UKNFpolska` through the seed mechanism (idempotent by URL, never overwriting), with `platform = youtube`, `active = false` and a schedule.

#### Scenario: Seeding twice
- **WHEN** the seed runs twice against the same database
- **THEN** the channel has exactly one `sources` row and it is inactive
