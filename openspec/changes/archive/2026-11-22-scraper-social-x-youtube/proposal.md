# Proposal

## Why

The brief names X and YouTube among the social media to collect, and the finfluencers of M1 live there. [ADR 0109](../../../.docs/decisions/0109-social-collectors-research.md) tested the routes on 2026-11-22: X posts come out of a cookie-based library (`Scweet` or `twscrape`, 20 posts of `@uknf` each), a YouTube watch page is readable through our own fetch layer without a login, and a Polish transcript comes out of `youtube-transcript-api` through a residential proxy. Telegram (`social-collection`) is the only social collector today, so the jury sees one platform.

## What Changes

- An X collector (`https://x.com/<handle>`): the newest posts of the account through a cookie-based library behind an adapter, authenticated with a dedicated account (`X_AUTH_TOKEN`, `X_CT0`, env only), from the home IP. One document per original post, platform `x`, author from the source URL.
- A YouTube collector (`https://www.youtube.com/@<handle>`): the newest videos from the channel page, one watch-page request per new video through our fetch layer, one document per video with title, description and, when obtainable, the transcript.
- Transcripts through `youtube-transcript-api` via a dedicated residential proxy (`YT_TRANSCRIPT_PROXY`, env only); a failed transcript keeps the video document without it.
- Dedicated flows: `run_source` dispatches X and YouTube by `source.platform` instead of the page-parser path; the robots check applies to the fetch-path flows only.
- Two seed rows (`@uknf` on X, `@UKNFpolska` on YouTube): active, without a schedule, so they run only on a scan request until the owner adds a cron.
- Pinned dependencies, scanned with `pip-audit` and listed in `.docs/security-audit.md`; `.env.example` entries for the new keys.
- **Exception, not a rule change:** the X flow does not read `robots.txt` (X disallows every path), and the transcript request uses its own proxy and no robots check; the owner approved this in ADR 0109 (effective when that ADR's PR merges, which must happen first). Web, Telegram and the YouTube page requests keep honouring `robots.txt`.
- **Conditional:** the YouTube group is cut from this change if the channel page cannot be read through our fetch layer (task 1.2); see `design.md`.

Out of scope, each a follow-up: local speech-to-text on audio and the PO-token server (proven in ADR 0109, heavy; if built, limited to short or already-suspicious videos), X videos and media files, replies and search, Facebook, Instagram and TikTok (coverage ADR), comments, re-scan change and removal tracking (issue 71), any dashboard or REST change. Owner: scraper (Adam).

## Capabilities

### New Capabilities
- `x-collection`: collect the newest posts of a public X account with a dedicated account's cookies, one document per post, bounded, and stopping at any sign of restriction.
- `youtube-collection`: collect the newest videos of a public YouTube channel, one document per video with title, description and optional transcript.

### Modified Capabilities
- `social-collection`: the registry may name a dedicated flow instead of a page parser; X and the transcript request are documented exceptions to the shared fetch path and robots rule; committed fixtures hold no credentials or tokens.

## Impact

- Code: `scraper/src/iw_scraper/social/` (new `x.py`, `youtube.py`, `transcript.py`), `collect.py` (dispatch by platform, robots check moved into the fetch-path flows), `social/registry.py`, `sources.py`/`pgstore.py` (a known-URL lookup), `config.py` and `app.py` (new keys), `seeds/sources.toml`, `requirements.txt`, `compose.yaml`, `.env.example`.
- Contract: touches none. `platform` already allows `x` and `youtube`; `scrape_meta.scraper` already allows `api`; `author`, `published_at` and `lang` (two letters or null) are existing fields. No REST route, no event.
- Docs: ADR 0109 is the decision record (docs-only PR, merged first), `.docs/status/scraper.md`, `.docs/security-audit.md`, `scraper/README.md` and `scraper/CLAUDE.md` for the env keys and the exception.
- Risk: the X account can be suspended at any time (X is suspending automation accounts since 2026-11-21, twscrape issue 384); the run ends as a recorded `blocked` error and never fails the stack.
