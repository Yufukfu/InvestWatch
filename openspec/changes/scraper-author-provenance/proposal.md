# Proposal

## Why

Issue #36: analytics routes a post to M2 (published by the firm itself) when `author.profile_url` or `author.handle` matches a registered firm. If the scraper took those from page-controlled markup (`<meta>`, `rel=author`, embedded JSON), an impersonator could fake a firm post. Reading `origin/main` shows that no collector sets `author` today, but `ingest.build_document` copies every key of the parsed page into the document, so an `author` dict from any future parser would be stored unverified.

## What Changes

- `build_document` drops `author` from the parsed page: the field is stored only when a platform collector supplies it from platform account data through a path added in that collector's own change.
- Document the provenance of `author.handle` and `author.profile_url` per platform in `scraper/README.md` and `scraper/CLAUDE.md`, and the trust rule in the contract notes (`.docs/integration-plan.md` §3).
- Out of scope: a `scrape_meta` flag for "author verified" (needs a contract change, proposal in the PR body and issue reply), the social collectors (`scraper-v2`), analytics routing.
- Owner: Adam's module (`scraper/`).
- Contracts: none changed. `author` is already optional and nullable in `ScrapedDocument` v1.

## Capabilities

### New Capabilities

### Modified Capabilities
- `document-ingest`: a document's `author` comes only from a trusted collector, never from the parsed page.

## Impact

- `scraper/src/iw_scraper/ingest/document.py` and its test; docs only otherwise.
