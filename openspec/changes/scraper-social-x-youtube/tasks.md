# Tasks

## 1. Gates (decide before any other group)

- [x] 1.1 Gate: install `scweet==5.8.3` in the scraper image, read its real API, count its real calls for one account, check display name and follower count are returned and `pip show` its dependencies; if it needs a browser or an unpinnable dependency or hides call control, switch to `twscrape==0.21.0` and write the switch into `design.md` decision 5
- [x] 1.2 Gate: through our fetch layer (scratch script in the scraper image, nothing committed) request the channel page of `@UKNFpolska` and one watch page; if the channel page ends in the consent redirect and a consent cookie in the identity does not fix it, cut group 4 and the YouTube seed from this change and say so in `design.md` decision 6, the proposal and ADR 0109's consequences
- [x] 1.3 Save the real responses as fixtures (`tests/fixtures/x_timeline_uknf.json`, `youtube_channel_uknf.html`, `youtube_watch_uknf.html`) with cookies, `visitorData`, tokens and viewer fields removed; the secret-scan test of group 2 must pass on them
- [x] 1.4 Pin the chosen X library and `youtube-transcript-api==1.2.5` in `requirements.txt`, run `pip-audit`, add the rows to `.docs/security-audit.md`

## 2. Dispatch, secrets and config

- [x] 2.1 Test first (`scraper/tests/test_social_dispatch.py`): a registration with no parser dispatches to its flow by platform; Telegram and web runs still read robots and use the identity, session and rotation; an X run reads no `robots.txt`, draws no identity and takes no proxy, but passes the URL guard and one `wait_turn`; a wrong URL or platform is `invalid_request` with no request
- [x] 2.2 Split `run_source` and `_collect` per flow: robots check inside the fetch-path flows, X flow before identity and proxy; `Registration.parse` optional; `Post.extra` and its pass-through in `build_page`
- [x] 2.3 Test first: secret scan of `scraper/tests/fixtures/` (`auth_token`, `ct0` with a value, a `cookie:` header, `visitorData`, `user:password@`); config reads `YOUTUBE_MAX_VIDEOS`, `YT_TRANSCRIPT_PROXY`, `X_AUTH_TOKEN`, `X_CT0` with validation, and no config error, log line, exception or traceback contains a value (reuse `ingest.errors.redact` and extend it to bare token values and proxy hosts where it does not cover them)
- [ ] 2.4 `config.py` readers, `app.py` wiring into the flows, `compose.yaml` pass-through (including the X library's telemetry switch if it has one), `.env.example` entries without values; check the image builds with the chosen library's native wheels (compose pass-through, `.env.example` and the wheel build are done; the `app.py` wiring waits for the flows of groups 3 and 4)
- [x] 2.5 Mutation check — mutations: 14 tried, 14 caught

## 3. X collector

- [x] 3.1 Test first (`scraper/tests/test_social_x.py`, fixture from 1.3, adapter's page function injected): URL validation, one document per original post with permalink and UTC `published_at`, `lang` outside two letters becomes null, reposts and textless posts skipped, malformed post skipped and all-malformed is one `parse_error`, scrubbed JSON `html`, `scrape_meta.scraper = api` and `post_id`, author from the URL, cookies missing, same post twice is one document
- [x] 3.2 Test first: one timeline call limited to `min(SOCIAL_MAX_POSTS, 40)` and no follower lookup when it returned nothing, a failed follower lookup leaves `followers` null, each restriction marker (auth failure, challenge, suspension, 429, empty not-found after success) ends the run as `blocked` with stored documents kept, an unknown library exception (message holding the cookie and the proxy host) becomes a job error without the secret anywhere and without a crash
- [x] 3.3 `social/x.py` adapter (call counting, exception mapping, `from None`) over the chosen library
- [x] 3.4 `social/x.py` flow (post to document mapping, author, ingest loop) and its registration
- [x] 3.5 Mutation check — mutations: 19 tried, 19 caught

## 4. YouTube collector (cut if gate 1.2 fails)

- [x] 4.1 Test first (`scraper/tests/test_social_youtube.py`, fixtures from 1.3): URL validation; video ids and channel id from the channel fixture capped by `YOUTUBE_MAX_VIDEOS`; consent redirect ends as `blocked_target`; a page with no ids is `parse_error` "no readable video list"; watch fixture gives title, description, publish date, channel name and caption track list; unplayable, wrong-channel and unreadable pages skipped, every page unreadable is one `parse_error`; a block ends the run
- [x] 4.2 `known_urls` lookup on the Postgres store behind a protocol, with a test against the test PostgreSQL (stored videos skipped, a stored video with transcript `failed` or `none` stays skipped)
- [x] 4.3 `social/youtube.py` list and watch parsers and the document build (scrubbed JSON `html`, `scrape_meta.video_id`, author from the URL, `transcript = none` until group 5)
- [x] 4.4 `social/youtube.py` flow (sequential watch requests with the per-domain wait, skip known, ingest loop) and its registration
- [x] 4.5 Mutation check — mutations: 19 tried, 19 caught

## 5. Transcripts (cut with group 4)

- [x] 5.1 Test first (`scraper/tests/test_social_transcript.py`, injected transcript function): text joined after title and description; Polish track preferred over English; no track or disabled is `none`; no proxy means no call, a "transcripts are off" log line and `none`; a block marks that video `failed`, stops transcripts for the run and the later videos are `none`; another error marks `failed` and the next video is still requested; the proxy URL is absent from every log and error
- [x] 5.2 `social/transcript.py` adapter over `youtube-transcript-api==1.2.5` (check the installed signature first; `GenericProxyConfig`, run in `asyncio.to_thread`, all exceptions mapped, `from None`) and its use in the YouTube flow
- [x] 5.3 Mutation check — mutations: 19 tried, 19 caught

## 6. Seeds and end to end

- [ ] 6.1 Test first (`scraper/tests/test_seed_social.py`): the X row (and the YouTube row unless cut) seeds once, twice is one row each, rows have no schedule and are not scheduled, a scan request starts a run; add them to `seeds/sources.toml`
- [ ] 6.2 End to end on the test stack (real Redis, PostgreSQL, MinIO) with the adapters' functions replaced by the saved fixtures: one X and one YouTube run store documents and publish events
- [ ] 6.3 One live run by hand with the cookies and proxy from `.env`; note the outcome in `.docs/status/scraper.md` (a failure there is reported, not hidden)
- [ ] 6.4 Mutation check — mutations: n/a, wiring group; behaviour verified by the end-to-end run

## 7. Closing

- [ ] 7.1 Apply iw-docs-update (`scraper/README.md` and `scraper/CLAUDE.md` env keys, the exception and how to stop a lost account, `.docs/status/scraper.md`, ADR 0109 link) and add the iw-ai-log row
- [ ] 7.2 Run iw-pr-review and fix real findings
