# Design

## Context

Telegram is collected through the shared fetch layer: `CollectorRegistry` maps a host to a `Registration` (platform, URL validator, parser `(bytes, url) -> Channel`) and `Collector._collect_social` pages and ingests (`scraper/src/iw_scraper/collect.py`). `run_source` draws an identity, opens a session and takes a proxy before `_collect` runs the robots check for every platform. The ingest requires a non-empty `html` and defaults `scrape_meta.scraper` to `httpx`. Evidence for what works on X and YouTube is in [ADR 0109](../../../.docs/decisions/0109-social-collectors-research.md); this design does not repeat it. Facts that shape it:

- X needs a logged-in cookie account; `Scweet` 5.8.3 returned 20 posts of `@uknf` in one timeline call (library call counts, display name and follower count were not measured). X disallows every path in `robots.txt` and is suspending automation accounts (twscrape issue 384).
- A YouTube watch page is readable through our fetch layer without a cookie (title, author, `publishDate`, description, caption tracks), one video only. The channel page through our fetch layer was a **302 to `consent.youtube.com`** in the plain-HTTP probe; only anonymous Playwright read it. The URL guard allows only the hosts of collectable sources, so that hop would end as `blocked_target`.
- The caption URL is refused from the home IP (429); `youtube-transcript-api` 1.2.5 returned 41 segments through a Polish residential proxy.
- `ScrapedDocument.platform` already allows `x` and `youtube`; `scrape_meta.scraper` allows `api`; `lang` must be two lowercase letters or null.

## Goals / Non-Goals

**Goals:**
- Two more social platforms with the least new machinery: reuse the registry, ingest, `SOCIAL_MAX_POSTS`, seed loader, queue and error set.
- The dedicated X account and the residential proxy are never put at risk by a loop: bounded calls, stop at the first restriction.
- Every secret stays in env and out of every log, error, document and fixture.

**Non-Goals:**
- Whisper and the PO-token server (a follow-up, limited to short or already-suspicious videos), X videos and media, replies, search, comments, other platforms, re-scan change tracking, any contract, REST or dashboard change.

## Decisions

1. **One change, dedicated flows.** `social/x.py`, `social/youtube.py` and `social/transcript.py` beside `telegram.py`. X and YouTube are not `Collector` parsers: `Registration.parse` may be `None` and then names the flow `run_source` dispatches by `source.platform`. The registration still carries platform and URL validator, so the existing `invalid_request` path for a wrong URL or platform keeps working (it needs no change). Alternative: two changes; rejected for the hand-in timeline.
2. **`collect.py` is split, not patched.** The robots check moves from `_collect` into the fetch-path flows (web, Telegram, YouTube pages). The X flow runs before `draw_identity`, `open_session` and the proxy rotation: it does the URL guard and one `wait_turn`, then the adapter, from the home IP (a changing IP for a cookie account raises the ban risk). Task 2.1 does this split with the existing tests as the safety net.
3. **`Post` gains `extra: dict` (default empty) for `scrape_meta` keys** (`video_id`, `transcript`, `post_id`, `scraper`); `build_page` passes it through. `platform` needs no plumbing: ingest takes it from `source.platform` (`build_page` never sets it). X posts use `message_id` for the numeric id too, so the existing `Post` fits.
4. **`html` is a scrubbed JSON subset, not the page.** X: the post as JSON with id, text, creation time, language, handle, media count. YouTube: player details, microformat and caption track list without `visitorData` or tokens. This satisfies the ingest's mandatory `html`, keeps rows small and keeps session data out of the store.
5. **X reads through a cookie library behind an adapter** (`fetch_posts(handle, limit) -> Page`). The adapter owns call counting (at most two page calls per run), maps library output to a small post type (including `lang` to two letters or null), maps every library exception to a `Reason` or a `restricted` result, and raises without the original as cause. The first task of the X group (gate) installs `scweet==5.8.3`, reads its real API, counts its real calls and checks that it returns display name and followers and what it needs (browser, native wheels). If it needs a browser or unpinnable dependencies, or hides call control, switch to `twscrape==0.21.0` before anything else and say so here. Playwright reading the page's GraphQL stays the documented fallback (proven in ADR 0109).
6. **YouTube list through the shared fetch layer, with a hard gate.** Task 1.2 requests `/@handle/videos` through our fetch layer. If it is readable (video ids and the channel id are in the page), the design stands. If it ends in the consent redirect (`blocked_target`) and a consent cookie in the identity does not fix it, **the YouTube group is cut from this change** and recorded as a follow-up that depends on the `scraper-v3-render` renderer (not yet built: `.docs/status/scraper.md`). This differs from ADR 0109's decision (list from anonymous Playwright) on purpose and is stated in the ADR consequences when it happens.
7. **Stored-video skip needs a lookup.** A `known_urls(urls) -> set[str]` method on the Postgres store (`pgstore.py`, behind a protocol so tests inject it) answers "which permalinks already have a document". A video with transcript `failed` or `none` is final: it is skipped next run and never updated. Accepted: it bounds paid proxy use.
8. **Video channel check by channel id.** The list page gives the channel id; a watch page's `videoDetails.channelId` must equal it, otherwise the video is skipped.
9. **Transcripts: `youtube-transcript-api` behind an injectable function, proxy by env** (`YT_TRANSCRIPT_PROXY` into `GenericProxyConfig`, run in `asyncio.to_thread` because the library is synchronous). Results: found, none (no track, disabled), block (stop for the run, `failed`), other error (`failed`, continue). Text is title, description and transcript in one document (analysis reads one text per document).
10. **Seeds need no loader change.** The seed loader accepts no `active` key and inserts `active = true`; the two rows carry no `schedule_cron`, so the scheduler skips them and only a scan request runs them. `source_kind = unknown`, `target_modules = [M1]` (the regulator's own accounts are the demo's neutral M1 source; the owner edits later in the dashboard).
11. **Suspension handling is the queue's.** A `blocked` result goes through the queue's existing block handling. No auto-deactivation (accepted); a lost account is handled by removing the schedule, written into `scraper/README.md`.
12. **Dependencies pinned and installed before use** (`scweet` or `twscrape`, `youtube-transcript-api==1.2.5`), scanned with `pip-audit`, rows in `.docs/security-audit.md`. Telemetry of the chosen X library is switched off by env in `compose.yaml` if it has any (twscrape documents `TWS_TELEMETRY=0`; check Scweet's own in the gate).

## Risks / Trade-offs

- **X suspends the dedicated account** (a wave began 2026-11-21): the run ends `blocked`, documents stay, nothing retries within the run; the seed has no cron, so a suspended account is not hit by a schedule until the owner adds one. Accepted: no automatic stop.
- **The X library's behaviour is measured only on success** (one call, 20 posts): the restriction mapping (challenge, suspension, 429, empty 404) is written from twscrape issue 384 and the library's source, and unit-tested against injected errors, not against X.
- **The YouTube channel page may not be readable through our client**: decision 6 makes this a cut, not a hope.
- **One sample everywhere**: every ADR 0109 result is one account or video and one residential session; the first live run after merge is the real test, so a failed run must read clearly in the job log.
- **Residential proxy is sticky for 30 minutes and costs money**: transcripts are optional, capped by `YOUTUBE_MAX_VIDEOS` and final per video.
- **Terms of X and YouTube are breached** and GDPR applies to stored public posts: stated in ADR 0109, accepted by the owner; no data leaves the stack.
- **Scraped text is untrusted input** that reaches the LLM: stored verbatim, never executed, never used to choose a URL (links are not followed).
