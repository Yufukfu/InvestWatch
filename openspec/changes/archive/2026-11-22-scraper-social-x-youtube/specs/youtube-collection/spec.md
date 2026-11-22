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
A run SHALL read the channel's video list once through the shared fetch layer, sending the fixed consent cookie `SOCS=CAI` with every YouTube page request (without it the channel page ends on the consent page), take the channel id and the newest `YOUTUBE_MAX_VIDEOS` video ids (default 10) from it, skip videos whose permalink already has a stored document, and request one watch page per remaining video, one at a time, each after the per-domain wait.

#### Scenario: Default cap
- **WHEN** a channel has 200 videos and `YOUTUBE_MAX_VIDEOS` is unset
- **THEN** one list request and at most 10 watch-page requests are made

#### Scenario: Nothing new
- **WHEN** every listed video already has a stored document
- **THEN** no watch page is requested

#### Scenario: Consent cookie sent
- **WHEN** a run requests the channel page or a watch page
- **THEN** the request carries the cookie `SOCS=CAI` and no other cookie

#### Scenario: List behind a consent page
- **WHEN** the channel page still redirects to `consent.youtube.com`, a host the URL guard does not allow
- **THEN** the run ends with the fetch layer's job error reason `blocked_target`, no document is emitted and no watch page is requested

#### Scenario: List without video ids
- **WHEN** the channel page is fetched but holds no video ids
- **THEN** no document is emitted and one job error with reason `parse_error` and the detail "no readable video list" is recorded

### Requirement: One document per video
The collector SHALL emit one document per playable video, with `url` `https://www.youtube.com/watch?v=<id>`, `platform` `youtube`, `source_kind` from the source row, `title` the video title, `published_at` the publish date in UTC ISO-8601, `lang` null, `canonical_url` equal to `url`, and `text` the title, the description and the transcript (when there is one) joined by blank lines.

#### Scenario: Video with transcript
- **WHEN** a video has the title `Film jubileuszowy…`, a description and a transcript
- **THEN** one document is emitted whose text starts with the title, followed by the description and the transcript, and `scrape_meta.transcript` is `caption`

#### Scenario: Video without caption track
- **WHEN** a video has no caption track
- **THEN** the document holds the title and the description and `scrape_meta.transcript` is `none`

#### Scenario: Unplayable video
- **WHEN** a watch page reports the video as unavailable, private or age-restricted
- **THEN** no document is emitted for it, the count is logged and it is not a job error

#### Scenario: Same video collected again
- **WHEN** the same video is collected in two runs
- **THEN** one document exists for it, and its transcript is not requested again

### Requirement: Video metadata and stored html
`scrape_meta.video_id` SHALL hold the video id and `scrape_meta.transcript` SHALL be `caption`, `none` or `failed`. `html` SHALL hold the video's player data (details, microformat and caption track list) as JSON, without `visitorData` or any token.

#### Scenario: Stored html holds no tokens
- **WHEN** a video is stored
- **THEN** its `html` parses as JSON and contains no `visitorData` key

### Requirement: Author comes from the source URL
Every document SHALL carry `author` with `handle` the source URL's handle with a leading `@`, `profile_url` `https://www.youtube.com/@<handle>`, `name` the channel name from the watch page's player data and `followers` null. `handle` and `profile_url` SHALL come from the source URL. A video whose channel id differs from the channel id read from the list page SHALL be skipped and counted.

#### Scenario: Author is a trusted argument
- **WHEN** a video is ingested
- **THEN** the author reaches ingest as its `author` argument and the page dict has no `author` key

#### Scenario: Video of another channel in the list
- **WHEN** a watch page's channel id differs from the list page's channel id
- **THEN** that video is skipped with a logged count

### Requirement: Transcript through a dedicated proxy
The collector SHALL request the transcript of a video once, through the proxy `YT_TRANSCRIPT_PROXY` (an HTTP proxy URL), preferring the original-language track and then any available track. A transcript, however it ends, SHALL be final: the video is not requested again. A missing `YT_TRANSCRIPT_PROXY` SHALL skip transcripts without a job error, log that transcripts are off and set `scrape_meta.transcript` to `none`.

#### Scenario: Proxy configured
- **WHEN** `YT_TRANSCRIPT_PROXY` is set and a video has a Polish caption track
- **THEN** the transcript is requested once through that proxy and its text is part of the document

#### Scenario: Original language first
- **WHEN** a video has a Polish and an English caption track
- **THEN** the Polish track is used

#### Scenario: Captions disabled or missing
- **WHEN** the library reports that the video has no usable transcript
- **THEN** `scrape_meta.transcript` is `none` and the document is stored

#### Scenario: Proxy not configured
- **WHEN** `YT_TRANSCRIPT_PROXY` is unset
- **THEN** no transcript request is made, a log line says transcripts are off and the documents carry title and description only

#### Scenario: Block on a transcript
- **WHEN** a transcript request is refused with an IP block or a rate limit, or the proxy stalls past the request timeout
- **THEN** that video's `scrape_meta.transcript` is `failed`, no further transcript is requested in the run, and the remaining videos are collected with `none`

#### Scenario: Other transcript failure
- **WHEN** a transcript request fails with a request error or an unknown library error
- **THEN** that video's `scrape_meta.transcript` is `failed` and the next video's transcript is still requested

### Requirement: Failures never produce a document
A watch page without readable player data SHALL be skipped and counted in the log. If every watch page of a run is skipped as unreadable, the run SHALL record one job error with reason `parse_error`. A block on a list or watch page ends the run with the fetch layer's job error and no retry in the same run. A document with empty `text` SHALL never be emitted.

#### Scenario: One unreadable watch page
- **WHEN** one watch page has no player data
- **THEN** that video is skipped with a logged count and the run goes on with the next video

#### Scenario: Every watch page unreadable
- **WHEN** no watch page of the run has player data
- **THEN** no document is emitted and one job error with reason `parse_error` is recorded

#### Scenario: Block on a watch page
- **WHEN** a watch page is answered as a block
- **THEN** the run ends, documents already stored stay and no further watch page is requested

### Requirement: The YouTube channel is seeded without a schedule
This change SHALL provide a YouTube `sources` row for `https://www.youtube.com/@UKNFpolska` through the seed mechanism (idempotent by URL, never overwriting), with `platform = youtube`, `source_kind = unknown`, `target_modules = [M1]` and no `schedule_cron`.

#### Scenario: Seeding twice
- **WHEN** the seed runs twice against the same database
- **THEN** the channel has exactly one `sources` row, with no schedule
