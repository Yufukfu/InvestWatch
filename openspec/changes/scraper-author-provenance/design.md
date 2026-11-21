# Design

## Findings (origin/main, 657e4a7)

- `parsing.parse_page` returns title, text, canonical URL and links; no author, handle or profile URL (`scraper/src/iw_scraper/parsing.py`).
- `document.build_document` (v1) emits no `author` key. `ingest.document.build_document` copies all other keys of the page dict into the document, so `author` (and `scrape_meta`) pass through unchecked.
- `ingest.validate` only checks that `author.profile_url` is an http(s) URL; it cannot tell where the value came from.
- `platform`, `source_kind` and `source_id` are copied from the `sources` row, never from the page.
- Telegram (unmerged `scraper/scraper-v2-social`, `social/telegram.py`) reads the channel handle from the `t.me/s/<handle>` preview markup, which is platform-rendered account data, but nothing there maps it to `author` yet.

## Decision

Treat `author` as untrusted when it arrives on the parsed page and drop it in `build_document`; the document then has no `author`, which the schema allows. A social collector that has platform account data (for example the Telegram channel handle and its `https://t.me/<handle>` URL) adds an explicit, separate path in its own change. This needs no contract change and fails safe: analytics sees `author` absent and cannot treat the post as the firm's own by author.

A positive "verified" signal (a `scrape_meta` flag) would let analytics tell "platform account" from "unknown", but it is a contract change (frozen, whole team); the proposal text is in the PR body.
