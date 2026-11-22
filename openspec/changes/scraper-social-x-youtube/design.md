# Design

## Context

Telegram is collected through the shared fetch layer: `CollectorRegistry` maps a host to a parser (`bytes, url -> Channel`), `Collector._collect_social` pages and ingests (`scraper/src/iw_scraper/collect.py`). Evidence for what works on X and YouTube is in [ADR 0109](../../../.docs/decisions/0109-social-collectors-research.md); this design does not repeat it. Facts that shape the design:

- X needs a logged-in cookie account; `Scweet` 5.8.3 returned 20 posts of `@uknf` in one timeline call. X disallows every path in `robots.txt`, and is suspending automation accounts (twscrape issue 384).
- A YouTube watch page is readable through our fetch layer without a cookie (`ytInitialPlayerResponse` with title, author, `publishDate`, description, caption tracks). The channel page through the fetch layer is **not proven** (anonymous Playwright reached it; our client was tested on a watch page only).
- The caption URL is refused from the home IP (429). `youtube-transcript-api` 1.2.5 returned 41 segments through a Polish residential proxy, with no PO token and no Node.
- `ScrapedDocument.platform` already allows `x` and `youtube`; Telegram uses `other` only because its enum value is missing.

## Goals / Non-Goals

**Goals:**
- Two more social platforms with the least new machinery: reuse the registry, ingest, paging cap, seed loader, queue and error set.
- The dedicated X account and the residential proxy are never put at risk by a loop: bounded requests, stop at the first restriction.
- Every secret (cookies, proxy URL) stays in env and out of every log, error and document.

**Non-Goals:**
- Whisper and the PO-token server (ADR 0109 proves them; they are a follow-up if the caption route breaks).
- X videos and media files, replies, search, comments, other platforms, any contract, REST or dashboard change.

## Decisions

1. **One change, two collector modules.** `social/x.py` and `social/youtube.py` beside `telegram.py`; both register in `registry` with their platform value and URL validator. Shared work (author, page dict, ingest loop) stays in `social/model.py`. One change because both need the same env, proxy and seed plumbing and one PR is cheaper than two. Alternative: two changes; rejected for the hand-in timeline.
2. **`Channel` and `Post` generalise by one field, not a new model.** `Post.message_id: int` stays for Telegram and X (X ids fit a 64-bit int); `Post` gains `extra: dict` (default empty) for `scrape_meta` keys (`video_id`, `transcript`, `post_id`). `Channel.network` is `telegram` for Telegram and null for platforms that have an enum value, and `build_page` sets `platform` from the registration. Alternative: a second model per platform; rejected, it duplicates `build_page` and the ingest loop.
3. **X reads through `Scweet` behind a thin adapter (`social/x.py`).** The adapter takes a timeline function so tests inject saved JSON; the real function calls `Scweet(cookies=...)`. The library maintains X's query ids and transaction ids itself. Alternatives: `twscrape` (richer model, two calls, more breakage reports; the adapter makes it swappable), Playwright reading the page's GraphQL (proven, kept as the documented fallback, heavier). First task of the X group checks the installed `Scweet` API and its dependency footprint (browser, native wheels); if it pulls a headless browser or unpinnable dependencies, the group switches to `twscrape` before any other work (decision gate in `tasks.md`).
4. **X bypasses the robots check; every other collector keeps it.** `_collect_social` runs the robots check for hosts of the fetch path only; the X path skips it and passes the URL guard and domain limiter. This is the owner's exception (ADR 0109), written into `social-collection` so the code is not a silent deviation.
5. **YouTube list and watch pages go through the shared fetch layer.** The collector asks for the channel page (`/@handle/videos`), extracts video ids from `ytInitialData`, drops stored ones (by permalink, through the store), then fetches up to `YOUTUBE_MAX_VIDEOS` watch pages sequentially, each a polite request. If the channel page redirects to the consent host (as in the anonymous Playwright and plain-HTTP probes), the run fails with a clear `parse_error`. That is the one unproven step: the first YouTube task is a test against a saved real channel page and a live check through the fetch layer; the fallback, only if the live check fails, is the renderer of `scraper-v3-render` for the list page alone.
6. **Transcripts: `youtube-transcript-api` behind an injectable function, proxy by env.** `YT_TRANSCRIPT_PROXY` (one residential HTTP proxy URL) is passed to `GenericProxyConfig`; the library is synchronous, so it runs in `asyncio.to_thread`. The text is title, description and transcript in one document (analysis reads one text per document). The transcript is optional: no proxy means no transcript, not an error. One block ends transcript requests for the run.
7. **`published_at` and `author` rules follow Telegram.** `author` is built from the source URL (trusted argument, never the page dict); X's display name and follower count and YouTube's channel name come from the platform's own fields.
8. **Seeds are inactive.** Two rows in `seeds/sources.toml` with `active = false`, so a stack without cookies never errors; the owner turns them on.
9. **Dependencies are pinned** (`scweet==5.8.3`, `youtube-transcript-api==1.2.5`), scanned with `pip-audit` and listed in `.docs/security-audit.md`. `scweet` telemetry, if any, is switched off by env in `compose.yaml` (twscrape documents `TWS_TELEMETRY=0`; check Scweet's own).

## Risks / Trade-offs

- **X suspends the dedicated account** (a wave began 2026-11-21): the run ends with `blocked`, documents stay, the queue's block handling applies and nothing retries in the same run. Mitigation: a low default frequency in the seed cron (every 6 hours), at most two timeline requests per run, one dedicated account only.
- **X's web build changes** and the library lags (twscrape issues 379 and 384): the adapter isolates the library; swap to `twscrape` or the Playwright route.
- **YouTube channel page through the fetch layer is unproven**: see decision 5; a failing live check changes the list step only.
- **Residential proxy is sticky for 30 minutes and costs money**: transcripts are optional and capped by `YOUTUBE_MAX_VIDEOS`; the proxy URL never reaches logs.
- **Terms of X and YouTube are breached** and GDPR applies to stored public posts: stated in ADR 0109, accepted by the owner; no data is shared outside the stack.
- **Scraped text is untrusted input** that reaches the LLM: stored verbatim, never executed, never used to choose a URL (links are not followed).
- **Sample size is one**: every ADR 0109 result is one account or video; the first live run after merge is the real test, so a failed run must read clearly in the job log.
