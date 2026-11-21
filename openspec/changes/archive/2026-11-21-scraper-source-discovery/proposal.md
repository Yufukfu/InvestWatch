# Proposal

## Why

Module M1 of the brief (section 2 of the challenge) is finding ads posted by third parties, especially finfluencers. Today every document comes from a URL a human vetted by hand; nothing proposes a new place to look, so the scraper behaves like a fixed URL list and not like a search system. The pages we already store carry the answer: each `documents` row keeps the outbound links of its page, and those links point at the sites that talk about or advertise the same products.

## What Changes

- A new command `python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]` (own entry module, like `iw_scraper.seed`): it reads the links stored in `documents.payload.links`, filters them and inserts the survivors into `sources` as **inactive candidates** for a human to approve.
- A candidate is one row per new host: `platform = web`, `source_kind = unknown`, `active = false`, `schedule_cron = null`, `name` prefixed `[candidate] `, `target_modules` copied from the sources of the documents that link to it. A human approves it in the dashboard (`PATCH /api/sources/{id}` already accepts `active`, `name` and `schedule_cron`), after which the existing collection rules apply unchanged.
- The command makes **no network call**: discovery reads what was already collected, so it adds no fetch, no SSRF surface and no change to the URL guard. A host enters the guard's allow-list only when a human activates its source.
- It is read-only on `documents`, insert-only on `sources`, idempotent (a host that any source already uses, active or not, is never proposed again), capped per run, and reports through the JSON logger.

**Out of scope:** re-fetching the seeded list pages; crawling; auto-activation; Telegram, X or YouTube channel candidates (those links stay pointers, and a channel candidate needs the social collector of `scraper-v2-social`, a follow-up once it merges); a dashboard screen for candidates (Kacper's `web/`); any edit to `collect.py`, `app.py` or `__main__.py`, which `scraper-v2-social`, `scraper-v3-render` and `scraper-stack` are changing; a new column or contract field. Owner: scraper (Adam).

**Touches:** no contract, no REST route, no event, no schema. It uses the existing `POST`-shape row in `sources` and the existing `PATCH /api/sources/{id}` for approval.

## Capabilities

### New Capabilities
- `source-discovery`: proposing inactive candidate web sources from the links of stored documents, with the filters, caps and idempotency that keep the allow-list and the human approval intact.

### Modified Capabilities
<!-- None: web-collection already makes an inactive source uncollectable, and rest-api already lets a client set `active`. -->

## Impact

- New `scraper/src/iw_scraper/discover.py` and `scraper/tests/test_discover*.py`; a run line in `scraper/README.md`; the scraper status file and the AI log row.
- Reads `documents` and `sources` through the existing `DATABASE_URL`; writes only new `sources` rows.
- New ADR (candidate shape and filters), written with the change.
- Depends on nothing in flight. Documents written by `scraper-v2-sources` and `scraper-v2-social` simply add more links to mine once those merge.
