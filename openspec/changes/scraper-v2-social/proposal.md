# Proposal

## Why

The challenge asks for collectors for social media, and module M1 (finfluencers) needs posts, not just pages. ADR 0103 left the first platform open. Four candidates were tried through our own fetch layer on 2026-11-21 (evidence in the ADR written by this change): Telegram's public channel preview is the only one that returns post text, time, author and permalink to an anonymous request and allows it in `robots.txt`. X disallows everything for non-search agents, Facebook and Instagram return login walls, TikTok returns a JavaScript shell, and YouTube disallows its feeds. The team decided on Telegram first.

## What Changes

- A Telegram collector for public channels read through `https://t.me/s/<handle>`: one `ScrapedDocument` per post, `platform = other` (the frozen v1 enum has no `telegram`), `source_kind` from the `sources` row, `published_at` from the post time, `author` from the channel header (name, `@handle`, profile URL, subscribers as `followers`).
- Paging with `?before=<id>` (20 posts a page), bounded by `SOCIAL_MAX_POSTS` (default 40) and by "a whole page of posts we already have".
- Posts that carry no text are skipped; a channel without a public preview is reported once and not retried.
- Links found in a post (including `x.com/<user>/status/<id>` and YouTube URLs) are kept in `links` as pointers and never fetched.
- Document identity for posts includes the permalink: for `platform != web` the ingest hashes `(canonical_url or url) + "\n" + normalised text`, so identical text at two permalinks is two documents and each ad keeps its exact URL (no schema, migration or index change; accepted by Damian on issue #34, with the contract description reworded in the closing task).
- Social collection goes through the same fetch layer, identity draw, proxy rotation, robots check, rate limit and URL guards as web pages (the brief asks for UA and proxy rotation in social collectors).
- The Telegram `sources` rows (`rarecryptosignals` M1 `third_party`; `crypto_sygnaly` and `SubeTradingPL` M3 `unknown`; `kdpwiadomosci` M1 neutral control) are seeded by this change.
- Follow-up only, no edit here: a `telegram` value for the `platform` enum, agreed by Damian for contract v2 after the hackathon (ten places, one a DB CHECK needing a migration); `scrape_meta.network = "telegram"` marks the network until then.
- A collector registry keyed by host, next to the page-parser registry, so a later platform is a module plus a `sources` row. `Source` selection learns that a `platform = other` source is collectable when a collector is registered for its host.
- ADR 0103 is decided here (Telegram), with the evidence and X and YouTube as later options.
- Out of scope: X, YouTube, TikTok, Facebook, Instagram, Playwright, downloading media, following links, analytics changes, the web `sources` seed rows (`scraper-v2-sources`), any contract change.
- Owner: Adam's module (`scraper/`).
- Contracts: produces `ScrapedDocument` v1 fields only; `published_at`, `author` and `links` already exist as optional fields. `scrape_meta` gets the extra keys `message_id`, `views` and `network` (the schema allows additional properties). No REST route or event is touched; the database is touched only through `scraper-ingest`.
- Depends on `scraper-orchestration` being merged: the run joins the pieces (`collect.py`), and this change adds a branch to it. Apply starts after that merge. It also seeds through the `scraper-v2-sources` loader, which scans every `*.toml` in `scraper/seeds/` and accepts any contract `platform` (design decision 13), and rebases onto `scraper-v3-render` if that merged first (both touch `collect.py`).

## Capabilities

### New Capabilities
- `social-collection`: collect posts of a public Telegram channel into contract-shaped documents, with paging bounds, per-post raw HTML and failure handling.

### Modified Capabilities
- `web-collection`: "Collect active sources only" now also accepts a `platform = other` source whose host has a registered social collector.
- `document-ingest`: "Deduplicate by content hash" hashes the canonical URL (else the URL) together with the text for `platform != web`; web documents hash as before.

## Impact

- New code under `scraper/src/iw_scraper/social/` (Telegram parser, collector registry) and a small branch in `collect.py` and `targets.py`/`types.py` selection; tests with saved real channel pages in `scraper/tests/fixtures/` (copied in the apply phase from the research samples in the session scratchpad).
- No new dependency (`lxml` is already used).
- Docs: `scraper/CLAUDE.md`, `iw-scraper-conventions`, `scraper/README.md` (`SOCIAL_MAX_POSTS`), `.docs/status/scraper.md`, ADR 0103 and its row in `.docs/decisions/README.md`.
