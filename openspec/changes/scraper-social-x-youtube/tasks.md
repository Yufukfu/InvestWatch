# Tasks

## 1. Platform plumbing and config

- [ ] 1.1 Test first (`scraper/tests/test_social_registry.py`): a registration carries its platform and URL validator; a source whose platform does not match its host is `invalid_request` with no request; Telegram behaviour unchanged
- [ ] 1.2 `Post.extra` (default empty) and `build_page` taking the platform from the registration; `config.py` reads `SOCIAL_MAX_POSTS` (existing), `YOUTUBE_MAX_VIDEOS`, `YT_TRANSCRIPT_PROXY`, `X_AUTH_TOKEN`, `X_CT0` with validation and a `redact` that never prints them; `compose.yaml` passes them through
- [ ] 1.3 Test: no config value, log line or exception text contains a cookie or proxy URL, including the invalid-value error paths
- [ ] 1.4 Mutation check — mutations: N tried, N caught

## 2. X collector

- [ ] 2.1 Decision gate: install `scweet==5.8.3` in the scraper image, read its real API and `pip show` its dependencies; if it needs a browser or an unpinnable dependency, switch to `twscrape==0.21.0` and note it in `design.md` before continuing
- [ ] 2.2 Test first (`scraper/tests/test_social_x.py`, fixture `tests/fixtures/x_timeline_uknf.json` saved from a real 20-post response, cookies removed): URL validation, one document per post with permalink and UTC `published_at`, reposts skipped and counted, textless posts skipped, malformed post skipped, author from the URL, cookies missing, restriction markers (401, challenge, suspension, 429) end the run as `blocked`, library error is a job error, no cookie in any message
- [ ] 2.3 `social/x.py` (adapter with an injectable timeline function, at most two timeline requests, stop on the first restriction) and its registration; `collect.py` skips the robots check for the X path and applies the URL guard and domain limiter
- [ ] 2.4 Test: second page only when the first brought a new post; `SOCIAL_MAX_POSTS` cap; same post twice is one document
- [ ] 2.5 Mutation check — mutations: N tried, N caught

## 3. YouTube collector

- [ ] 3.1 Live check through the fetch layer (scratch script, nothing committed): the channel page of `@UKNFpolska` and one watch page; save both real responses as fixtures (`tests/fixtures/youtube_channel_uknf.html`, `youtube_watch_uknf.html`); if the channel page redirects to the consent host, note it and use the renderer for the list page only
- [ ] 3.2 Test first (`scraper/tests/test_social_youtube.py`): URL validation; video ids from the channel fixture capped by `YOUTUBE_MAX_VIDEOS`; stored videos skipped; watch fixture gives title, description, publish date, channel name and caption track list; unplayable, wrong-channel and unreadable watch pages skipped as specified; consent redirect is `parse_error` "no readable video list"; a block ends the run
- [ ] 3.3 `social/youtube.py` (list parse, watch parse, document build with `scrape_meta.video_id`) and its registration; sequential, rate-limited watch requests
- [ ] 3.4 Mutation check — mutations: N tried, N caught

## 4. Transcripts

- [ ] 4.1 Test first (`tests/test_social_youtube_transcript.py`, injected transcript function): text joined after title and description; no caption track is `none`; no proxy means no transcript call and `none`; the first block marks that video `failed`, stops transcripts for the rest of the run (the other videos are `none`) and the documents are still stored; proxy URL absent from every log and error
- [ ] 4.2 Adapter over `youtube-transcript-api==1.2.5` (`GenericProxyConfig`, original-language track first) run in `asyncio.to_thread`; check the installed signature first
- [ ] 4.3 Mutation check — mutations: N tried, N caught

## 5. Seeds, dependencies, end to end

- [ ] 5.1 Test first (`tests/test_seed_social.py`): the two inactive rows seed once, twice is one row each, inactive rows are not scheduled; add them to `seeds/sources.toml`
- [ ] 5.2 Pin `scweet` (or `twscrape`) and `youtube-transcript-api` in `requirements.txt`, run `pip-audit`, add the rows to `.docs/security-audit.md`
- [ ] 5.3 End to end on the test stack (real Redis, PostgreSQL, MinIO) with the adapters' functions replaced by the saved fixtures: one X and one YouTube run store documents and publish events; the opt-in live check (`IW_LIVE_SOCIAL=1`, cookies and proxy from `.env`) is run once by hand and its outcome noted in the status file
- [ ] 5.4 Mutation check — mutations: n/a, wiring group; behaviour verified by the end-to-end run

## 6. Closing

- [ ] 6.1 Apply iw-docs-update (`scraper/README.md` and `scraper/CLAUDE.md` env keys and the exception, `.docs/status/scraper.md`, ADR 0109 link) and add the iw-ai-log row
- [ ] 6.2 Run iw-pr-review and fix real findings
