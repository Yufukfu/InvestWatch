# 0109. Social collectors for X and YouTube: research and probes

- Status: accepted
- Date: 2026-11-21 (probes and decision continued on 2026-11-22)
- Deciders: Adam (scraper module)

## Context

The brief asks for collectors for social media with User-Agent and proxy rotation and no paid external API. ADR 0103 chose Telegram first (PR #61) and recorded that X, Facebook, Instagram, TikTok and YouTube feeds failed a plain anonymous fetch: X `robots.txt` is `Disallow: /`, the syndication timeline answered 429, `api.x.com` answered 401, YouTube `/feeds/videos.xml` is disallowed, channel pages redirect to a consent page. Decision for this research (Adam, 2026-11-21): no paid API; data scraping only. A free API key is therefore out; so were accounts and logins, until the exception recorded under Decision on 2026-11-22.

## Probe plan (channels named before any request)

Public official accounts of the regulator, handles cross-checked on three independent secondary sources (not yet confirmed against a link on `knf.gov.pl`):

- X: `https://x.com/uknf` ("Urząd KNF").
- YouTube: `https://www.youtube.com/@UKNFpolska`.

Rules for the probes of 2026-11-21 (the authenticated, `yt-dlp` and proxy probes of 2026-11-22 ran under the owner's exception, see Decision): 1-2 requests per technique, at least 5 s apart, our identity layer, `robots.txt` read first and honoured (a Disallow is a stop, for a browser as much as for an HTTP client: Playwright is a different fetch layer, not a different permission), no login, no cookies carried over, responses saved outside the repo.

Techniques to probe, each against the channels above:

1. HTTP client (`noble-tls`) on pages and endpoints that `robots.txt` allows: YouTube watch and channel pages, oEmbed; X syndication host (own `robots.txt` read first).
2. `yt-dlp` as a metadata extractor (`--dump-json --flat-playlist`, no media).
3. InnerTube (`youtubei/v1`) as `yt-dlp` uses it; maintained InnerTube libraries only as a reading aid.
4. Playwright (headless Chromium) on the same allowed URLs, to see what a rendered page gives that HTTP does not (consent page, lazy lists).
5. X through a browser or guest GraphQL: only if X `robots.txt` allows the path; the current `Disallow: /` means the probe is a `robots.txt` read only.

## Evidence (probes 2026-11-21, one to two requests each, scratchpad only)

| Technique | Result |
|---|---|
| `robots.txt` of `x.com`, `cdn.syndication.twimg.com`, `syndication.twitter.com` | `User-agent: *` / `Disallow: /` on all three; only Googlebot, Bingbot and `facebookexternalhit` have allow rules. |
| `robots.txt` of `www.youtube.com` | Disallows `/youtubei/` (InnerTube), `/results` (search), `/feeds/videos.xml`, `/api/`, `/comment`, `/live_chat`, `/timedtext_video`. Does not disallow channel pages, `/watch` or `/oembed`. |
| HTTP client on `youtube.com/@UKNFpolska/videos` | 302 to `consent.youtube.com` (EU consent), no data. |
| Playwright (headless Chromium) on the same URL | Passed the consent page with the visible "Odrzuć wszystko" button, landed on the channel, 1.8 MB rendered HTML with 30 `/watch?v=` links and `ytInitialData`. Titles and ages sit in the new `lockupViewModel` markup; a parser for them was not written. |
| Playwright on one watch page (3 attempts, one video) | Failed: the saved page stayed the consent interstitial ("Zanim przejdziesz do YouTube") with no player response, although the same click worked on the channel page. Three variants of the consent step did not change it, so the cause is unknown; stopped per the same-failure-twice rule. The channel page is the only proven YouTube route. |
| Authenticated X: Playwright with `auth_token` and `ct0` of a dedicated account (owner's proposal, probed once 2026-11-22) | Works. `https://x.com/uknf` returned 200 and, from the rendered DOM, the newest posts with text, `time[datetime]`, permalink (`/uknf/status/<id>`) and author handle (4 of 4 articles parsed; one pinned post from 2025-09-30, three from 2026-11-20). Overrides X's `robots.txt` and breaches its terms; ban risk to the account. |
| Authenticated YouTube: Playwright with the logged-in `cookie:` header of a dedicated account (probed twice on one video) | Works. The watch page returned `ytInitialPlayerResponse` with `playabilityStatus` OK, title, author, `publishDate`, a description and one caption track (`pl:asr`, auto-generated). The consent interstitial that blocked the anonymous run did not appear. |
| Our own fetch layer (`iw_scraper.fetch`, `noble-tls`, drawn identity, run in the scraper image, one request each, 6 s apart) | YouTube watch page: 200 with `ytInitialPlayerResponse` (OK, title, author, `publishDate`) both with the cookie header and without it; no consent redirect. `/watch` is allowed by `robots.txt`, so YouTube metadata needs neither a browser nor a login. X profile with the cookies: 200, but a 317 KB JavaScript shell without tweets (`tweetText` absent), so X needs a browser or its web GraphQL API. The GraphQL route is not proven: the shell lists two `main.js` bundles, but our fetch layer refuses a non-HTML body (`parse_error`, `application/javascript`), so the bearer token and query ids could not be read through it. A collector would need a fetch option for JSON and JavaScript bodies. The same client's caption request answered 429 as well (fourth 429 in total, all from the same IP). |
| X: Playwright with the cookies, listening to the page's own GraphQL responses (`UserTweets` / `UserOriginalsTimeline`), one page load plus one scroll, 2026-11-22 | Works and is the efficient route: 20 tweets from `@uknf` as structured JSON (`rest_id`, `legacy.full_text`, `created_at`, `lang`, media with `video_info.variants`), no DOM selectors, and no need to track the rotating `doc_id`s because the browser sends them. No video was found among those 20 posts (video fields parse from `extended_entities`, not yet seen populated). The page issues about ten other GraphQL calls (all 200). |
| yt-dlp 2026.10.26, `pl-orig` auto captions, no download, in the scraper image (python 3.12), 2026-11-22 | Home IP, default clients: "This video is not available". `web` client: HTTP 429 on the caption. Same with `bgutil-ytdlp-pot-provider` 2.0.2 (HTTP server, "gvs" token generated), with Node 18 (too old for the challenge solver) and with the logged-in cookies: still 429, and no audio formats ("Only images are available"). |
| Same, through 3 of the 1000 datacenter HTTP proxies (no cookies) | All three: "Sign in to confirm you're not a bot"; worse than the home IP. |
| Same, through Polish residential proxies (`marsproxies`, sticky 30 min sessions) | Default clients: "This video is not available". `web` client: no 429; yt-dlp reports "missing subtitles languages because a PO token was not provided". Two later runs (web client, with the PO token server) failed with "Did not get any data blocks" (proxy-level failure, not a YouTube answer). Captions through a residential IP plus a PO token are therefore not proven, not disproven. |
| Audio route, 2026-11-22: `yt-dlp -f 140` through a Polish residential proxy, Node 22 and the bgutil PO token server, then `faster-whisper` `large-v3-turbo` int8 on CPU, `language=pl`, VAD on | Works. `-F` listed audio-only formats (opus, m4a) for the first time; the 1.7 MB m4a (107 s) downloaded; model load 62 s, transcription 28 s for 107 s of audio, 10 segments of accurate Polish, names and numbers intact in the sample read. One video, one residential session, no cookie, no account. Needs Node 20+, the token server container and a residential IP (datacenter proxies were refused as bots, the home IP got 429 on captions). |
| Caption track fetch (`captionTracks[0].baseUrl&fmt=json3`, same cookie) | HTTP 429 "Sorry..." page. A block signal: stopped, not retried. A transcript through this URL is not proven; the "Show transcript" panel was not found on the page either. |
| Sources read, not probed | Vendor and blog reports (Scrapfly 2026-11-16, 2026-10-08): anonymous X guest access is shut, `doc_ids` rotate every 2-4 weeks, `twscrape`, `Scweet`, `twikit` need logged-in accounts, Nitter archived after an X cease-and-desist (2026-08-24), official API is pay-per-use. `yt-dlp` and InnerTube libraries read YouTube through `/youtubei/`. |

## Options considered

Judged under the original rules (honour `robots.txt`, no login); the Decision below supersedes the first two.

- **X, any client or browser:** every X host is disallowed by `robots.txt`; the techniques that work need accounts. Rejected under the original rules; accepted under the 2026-11-22 exception, by browser (proven).
- **YouTube via `yt-dlp` or InnerTube:** reads `/youtubei/` and `/api/`, which `robots.txt` disallows. Rejected under the original rules; the only route that produced audio, so accepted under the exception for transcripts.
- **YouTube via our fetch layer on `/watch`:** allowed path, no login, no key; proven for metadata on one video.
- **YouTube via Playwright, anonymous:** channel pages work (30 video links); watch pages did not (consent interstitial, 3 attempts).
- **Facebook, Instagram, TikTok:** not re-probed; login walls or JavaScript shells (ADR 0103).

## Decision

Adam, 2026-11-22: no paid API; scraping only; logging in with a dedicated account is allowed, with its cookies kept in the untracked `.env` (`X_AUTH_TOKEN`, `X_CT0`, `YT_COOKIE_HEADER`), and `yt-dlp`'s use of `/youtubei/` and `/api/` is allowed for YouTube audio. This is an explicit exception to the "no login, honour `robots.txt`" rule; it applies to the research done on 2026-11-22 and, if the human approves this ADR, to follow-up collectors. The login is proven necessary only for X.

- **X:** Playwright with a dedicated account's cookies, reading the page's own GraphQL responses (proven on `@uknf`, tweets only; video links not yet seen).
- **YouTube metadata** (title, author, date, description, caption track list): our own fetch layer on `/watch`, no login (proven on one video). The channel's video list: anonymous Playwright (30 links; the parser for titles and ages is not written).
- **YouTube transcripts:** the caption URL is blocked (429 from the home IP in every setup); the proven route is local speech-to-text on the audio, fetched through a residential proxy with Node 22 and a PO token server (proven on one video).
- Nothing else is exempted: still read-only, low rate, public accounts only, a block signal (429, captcha, login challenge) ends the run and is not retried.

## Consequences

- Follow-up changes `scraper-social-x` and `scraper-social-youtube` depend on the renderer from `scraper-v3-render`. Cookies are read from env only, never logged, never passed through job payloads or `scrape_meta`; a 401 or a login challenge ends the run and raises a health flag, because the cookie has expired or the account is locked.
- Account risk: a throwaway account can be locked at any time; the collector must degrade to "source unavailable", not fail the stack. Terms of X and YouTube are breached; GDPR applies to the stored public posts.
- Transcripts for scam analysis: the caption URL answered 429 from the home IP every time (our fetch layer, the browser's player request, `yt-dlp`). Desk research (subagent, 2026-11-22, read from sources only, nothing run; claims are other people's reports): the likely cause is a missing PO token on the caption URL (`exp=xpe`, `pot=` and `c=` parameters in yt-dlp's code), and auto-translated tracks are throttled harder than the original-language track (yt-dlp issue 13831, still open 2026-11-14, comments report `--sub-langs ".*-orig"` working). Ranked options to test, in order: (A) `yt-dlp --skip-download --write-auto-subs --sub-langs "pl-orig"` (Unlicense, Python 3.11+, release 2026.10.26); (B) the same with `bgutil-ytdlp-pot-provider` 2.0.2 (needs Node; open timeout and memory-leak issues); (C) local `faster-whisper` on downloaded audio (large-v3 is among the top systems for Polish in BIGOS V2, hallucinates on silence or music, needs VAD; audio download may itself need a token). `youtube-transcript-api` 1.2.5 has no PO-token support and is skipped; public Invidious and Piped instances are unreliable; reading the transcript panel in a browser is the weakest route. All of A-C call `/youtubei/` or `/api/`, so they rely on the robots.txt exception above. Experiments (table above): A (`yt-dlp` captions) got 429 from the `web` client on the home IP; B (plus the PO token server) did not help there, even with cookies; datacenter proxies were refused as bots; a residential proxy removed the 429 on captions. C worked: audio through a residential proxy, Node 22 and the PO token server, transcribed by `faster-whisper`. Transcripts are therefore feasible, at the cost of a residential proxy, a Node and token-server container and CPU time (about 0.3 s of compute per second of audio for `large-v3-turbo` int8 in this run, plus a 1.6 GB model); the caption URL route stays unavailable. Proven on one video only.
- No new dependency now (`playwright-core` was only used in the scratchpad); the collectors add the renderer's.
- The jury gets the evidence trail: what failed anonymously and why, what works with an account.
