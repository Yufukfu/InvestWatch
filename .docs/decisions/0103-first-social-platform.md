# 0103. First social platform

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from research done on 2026-11-21; the choice of Telegram was made by the human the same day; accepted by the human via the PR that carries `scraper-v2-social`

## Context

Team decision: collect from one social platform first, more only if time allows. The challenge brief asks for collectors with user-agent and proxy rotation for social media and names Facebook, Instagram and TikTok as examples ("m.in."); module M1 needs posts, not only pages. The contract's `platform` enum allows `facebook|instagram|tiktok|youtube|x|forum|other` (`.docs/integration-plan.md` §3) and is frozen. The rules of the scraper (`scraper/CLAUDE.md`) require a robots-allowed, anonymous request through our own fetch layer with its identity and proxy rotation, and an on-premise stack with no paid API ([`../../CLAUDE.md`](../../CLAUDE.md)).

## Options considered

Each candidate was requested once or a few times through the production fetch layer (our `noble-tls` identity, about 5 s apart) on 2026-11-21.

1. **X (x.com).** `robots.txt` is `User-agent: *` / `Disallow: /`; the syndication timeline answered 429; `api.x.com` answered 401; the official API is pay-per-use at $0.005 per post read with no free tier ([pricing](https://docs.x.com/x-api/getting-started/pricing)). Nitter and XCancel are gone after a cease-and-desist in August 2026; RSSHub needs a cookie or key; third-party providers sell trial credits and scrape against X's terms. A browser would still ignore `robots.txt` and meet login walls. Not compliant.
2. **Facebook and Instagram.** HTTP 200 but a login-wall shell with no posts.
3. **TikTok.** A 409 KB JavaScript shell (`statusCode 10221`); it would need Playwright and was not verified with a real profile.
4. **YouTube.** `/feeds/videos.xml` is disallowed by `robots.txt`; channel pages redirect to a consent page; oEmbed returns only title and author. The Data API v3 is a possible later route (terms, quota and key not checked).
5. **Wykop (forum).** Server-rendered, but a weak source for M1 finfluencer content.
6. **Telegram public channels (`https://t.me/s/<handle>`).** HTTP 200 with 100 to 160 KB of server-rendered HTML holding post text, ISO time, permalink and the channel header; `t.me/robots.txt` is 404 (no restriction); `?before=<id>` pages 20 posts at a time; about 25 requests at 5 s spacing brought no 429. Four Polish channels were fetched (`rarecryptosignals`, `crypto_sygnaly`, `SubeTradingPL`, `kdpwiadomosci`); their content was not reviewed for violations.

## Decision

Telegram public channels first, decided by the human on 2026-11-21. It is the only candidate that answers an anonymous, robots-allowed request with post text, time, author and permalink through our existing fetch layer, with no login, no browser and no paid API. X, Facebook, Instagram, TikTok and YouTube were each refused, walled or JavaScript-only on the evidence above. Documents carry `platform = other` because the frozen enum has no `telegram` value, with `scrape_meta.network = "telegram"` marking the network (Damian agreed to add the enum value in contract v2 after the hackathon, issue 34).

## Consequences

- One collector module under `scraper/src/iw_scraper/social/` and a registry keyed by host; a later platform is a new module, one registration and a `sources` row, with no change to the run, ingest or the contract. X stays out unless a paid API is accepted by an exception ADR; YouTube through the Data API v3 would be its own change after a terms check.
- The brief's Facebook, Instagram and TikTok are not covered. This is a gap against the brief, stated in the design of `scraper-v2-social`.
- Telegram's terms for on-premise collection of public channels were not researched. Only the public preview is read, politely, with no login. Channels can switch the preview off, and the preview shows fewer posts than the channel has.
- The author handle is parsed from preview HTML, not an API; provenance is recorded in `scraper/README.md`, "Author provenance".
- Revisit when the contract adds a `telegram` platform value, or if Telegram changes its preview markup (a change shows up as `parse_error`; the opt-in live smoke test is the canary).
