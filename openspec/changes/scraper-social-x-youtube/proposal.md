# Proposal

## Why

The brief names X and YouTube among the social media to collect, and the finfluencers of M1 live there. [ADR 0109](../../../.docs/decisions/0109-social-collectors-research.md) tested the routes on 2026-11-22: X tweets come out of a cookie-based library (`Scweet` or `twscrape`, 20 tweets of `@uknf` each), YouTube metadata comes out of our own fetch layer without a login, and a Polish transcript comes out of `youtube-transcript-api` through a residential proxy. Telegram (`social-collection`) is the only social collector today, so the jury sees one platform.

## What Changes

- A collector for X accounts (`https://x.com/<handle>`): the newest posts of the account through `Scweet`, authenticated with the cookies of a dedicated account (`X_AUTH_TOKEN`, `X_CT0`, env only). One document per post with text, `platform` `x`, a trusted author from the source URL.
- A collector for YouTube channels (`https://www.youtube.com/@<handle>`): the newest videos from the channel page, one watch-page request per new video through our fetch layer, one document per video with title, description, channel as author and, when available, the transcript.
- Transcripts through `youtube-transcript-api` via a dedicated residential proxy (`YT_TRANSCRIPT_PROXY`, env only); a failed transcript keeps the video document without it.
- Two seed sources (`@uknf` on X, `@UKNFpolska` on YouTube) behind the existing seed loader, inactive until the owner turns them on.
- Pinned dependencies (`scweet`, `youtube-transcript-api`), scanned with `pip-audit` and listed in `.docs/security-audit.md`.
- **Exception, not a rule change:** the X collector does not read `robots.txt` (X disallows every path) and both collectors use a login or a proxy outside the rotation; the owner approved this in ADR 0109. Web and Telegram collectors keep honouring `robots.txt`.

Out of scope: local speech-to-text (Whisper) on audio and the PO-token server (proven in ADR 0109, heavy: Node, a token container, CPU; a follow-up change if the caption route breaks), X videos and media files, replies and search, Facebook, Instagram and TikTok, comments, any dashboard or REST change. Owner: scraper (Adam).

## Capabilities

### New Capabilities
- `x-collection`: collect the newest posts of a public X account with a dedicated account's cookies, one document per post, bounded, paced, and stopping on any sign of suspension.
- `youtube-collection`: collect the newest videos of a public YouTube channel, one document per video with title, description and optional transcript.

### Modified Capabilities
- `social-collection`: the registry of collectors by host gains collectors that do not run on the fetch layer's page parse, and the `platform` value of a social document is `x` or `youtube` when the contract enum has it (Telegram stays `other`).

## Impact

- Code: `scraper/src/iw_scraper/social/` (new `x.py`, `youtube.py`), `collect.py` (dispatch by platform), `config.py` (env keys), `seeds/sources.toml` (two inactive rows), `requirements.txt`, `compose.yaml` (env pass-through).
- Contract: touches none. `platform` already allows `x` and `youtube` (`.docs/integration-plan.md` §3); `author`, `scrape_meta` and `published_at` are existing fields. No REST route, no event.
- Docs: ADR 0109 is the decision record (separate docs-only PR, linked), `.docs/status/scraper.md`, `.docs/security-audit.md`, `scraper/README.md` and `scraper/CLAUDE.md` for the env keys and the exception.
- Risk: the X account can be suspended at any time (X is suspending automation accounts since 2026-11-21, twscrape issue 384); the collector degrades to a recorded job error and never fails the stack.
