# Design

## Context

`scraper-v1` fetches one URL and parses it into one `ParsedPage` through a registry keyed by host. `scraper-orchestration` adds `run_source` (`collect.py`), which joins guards, robots, fetch, parse and `Ingestor.ingest(page, source, ...)`. A Telegram channel page holds up to 20 posts, so one fetch yields many documents and one run may need several fetches. The research on 2026-11-21 (scratchpad samples of 12 channel pages and a `?before=2000` page, taken with our `noble-tls` identity, about 5 s apart) found: HTTP 200 and 100 to 160 KB of server-rendered HTML, no `robots.txt` (404, so allowed), no 429 in about 25 requests.

## Decisions

1. **A collector registry beside the parser registry.** `PageParser` returns one `ParsedPage`, which cannot express "many posts plus a next page". A second registry, `social.registry`, maps host to a collector module with `parse(body, final_url) -> Channel` (header plus posts plus the `before` link). It copies the registry's rules (key by host with `www.` equivalence, refuse duplicates). `run_source` asks it first when `source.platform != "web"`. Rejected: widening `ParsedPage` for every site.
2. **`Source.collectable` is `active and (platform == "web" or a collector accepts the host)`.** The check stays a pure function; the registry's host set is passed in. No `FETCH_EXTRA_HOSTS` entry is needed, because the allow-list is built from the hosts of collectable sources (`UrlGuard.for_sources`) and a Telegram source puts `t.me` on it. A source whose redirect leaves `t.me` is refused by the existing guard.
3. **`platform = other`.** The contract v1 enum has no `telegram` and is frozen. `other` is the only honest value. Telling Telegram sources apart is by host, not by platform. A future `telegram` value would be a contract change for the whole team.
4. **Per-post HTML.** `iw-raw` holds the markup of the one message wrapper (a few KB), not the 100 to 160 KB page copied 20 times. The source of the `ingest` page dict's `html` is the serialised wrapper.
5. **Stateless paging.** No stored cursor, so no schema change. A run reads the newest page, then `?before=<id>` from the page's `tme_messages_more` link, up to `SOCIAL_MAX_POSTS` (default 40, two pages). It stops early when every post that has text on a page returns `duplicate` from ingest, which makes a rerun of a quiet channel cost one request.
6. **Dedup is per source and text** (`document-ingest`). A promo reposted verbatim in the same channel is one document; the first permalink wins. Accepted: a repeated identical text adds nothing for analysis.
7. **Links are data.** Anchors and bare URLs go to `links` as `{href, text}`. `x.com` and YouTube links are pointers for analytics and reviewers; the collector never requests them (the guard would refuse them anyway, as they are not allow-listed hosts).
8. **Followers.** `36.1K` is 36100 and `1.2M` is 1200000; the value is rounded to the nearest integer. The counter is an approximation shown by Telegram, which is what the contract's `followers` carries for other platforms too.
9. **Selectors** (from the saved pages): message wrapper `tgme_widget_message_wrap`; id from `data-post` (`<handle>/<id>`); text `tgme_widget_message_text` (not the reply preview); time `<time datetime>`; permalink `tgme_widget_message_date` href; views `tgme_widget_message_views`; header `tgme_channel_info_header_title`, `..._username`, `tgme_channel_info_counters`; older posts `a.tme_messages_more`. A change of Telegram's markup shows up as `parse_error` (no header and no posts), not as empty documents.
10. **Failures reuse the closed reasons** of `web-collection`: nothing new is added. "No public preview" is `parse_error` with that detail, "wrong URL form" is `invalid_request`.

## ADR

ADR 0103 is written in the docs task as accepted: context, the options with this evidence (X: `robots.txt` `User-agent: * / Disallow: /`, the syndication timeline 429, `api.x.com` 401, official API pay-per-use at $0.005 per post read; Facebook and Instagram: 200 login-wall shells; TikTok: a 409 KB JavaScript shell with `statusCode 10221`; YouTube: `/feeds/videos.xml` disallowed by `robots.txt`, channel pages redirect to a consent page, oEmbed gives title and author only; Wykop: server-rendered but weak for M1; Telegram: the findings above), the decision (Telegram, decided by the human on 2026-11-21) and the consequences. X and YouTube stay later options: X only through a paid API with an exception ADR, YouTube through the Data API v3 as an optional later change (terms and quota not checked).

## Risks

- Telegram's terms for on-premise collection of public channels were not researched. Only the public preview is read, politely, with no login.
- Channels can switch the preview off, VIP content is unreachable, and the preview may show fewer posts than the channel has.
- Post text and authorship are untrusted input: stored as text, never rendered as HTML downstream by this module.
- Whether the seed channels contain content that violates the challenge's rules was not reviewed; they are inputs, not findings.

## Open questions

- Should `scrape_meta.views` be kept (an engagement signal for analytics) or dropped to keep `scrape_meta` to the fetch fields? Kept here; trivial to remove.
- `scraper-v2-sources` is expected to seed `t.me/s/rarecryptosignals`, `crypto_sygnaly`, `SubeTradingPL` and `kdpwiadomosci` as `third_party`, `M1`/`M3`; agree the rows with that change.
