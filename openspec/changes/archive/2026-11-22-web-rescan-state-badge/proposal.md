# Proposal

## Why

Module 1 of the brief asks for a periodic update mechanism. Since `api-rescan-state` (PR #87) the api derives whether a flagged page changed or disappeared after the finding and serves it on the finding detail as `document.scrape_meta.rescan` `{state, latest_document_id, checked_at}`. The dashboard does not show it yet, so an analyst cannot tell that an ad was edited or taken down (issue #71, web part).

## What Changes

- The finding detail panel shows a badge and one line from `document.scrape_meta.rescan.state`:
  - `changed`: badge "Zmieniona" and a line that the page changed since the finding, naming the newer version's document id (`latest_document_id`) and when it was observed (`checked_at`);
  - `removed`: badge "Usunięta" and a line that the page is gone since the finding, with `checked_at`.
- A missing `rescan` key (the contract mock server, older api), `current`, or any value the web does not know shows nothing.
- `scrape_meta` is an open object written from scraped data, so the data hook parses `rescan` defensively: only a known `state`, a UUID `latest_document_id` and a parseable `checked_at` reach the view model; anything else is dropped.

Out of scope: a badge in the findings list (needs an optional `Finding` field, a contract change; deferred in `api-rescan-state` follow-ups), and the scraper records that make `removed` appear (scraper, PR #108).

Module: `web/`. Touches no contract, REST route or event: it reads the existing `GET /findings/{id}` response (`contracts/openapi.yaml`, `scrape_meta` is `additionalProperties: true`).

Spec pre-approved by Kacper via the issue request (#71).

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-findings`: the finding detail shows the re-scan state of the finding's page.
