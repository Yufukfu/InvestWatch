## MODIFIED Requirements

### Requirement: Finding detail with its document
`GET /api/findings/{id}` SHALL return the finding with `risk_level`, its `document` in the `ScrapedDocument` shape, and `screenshot_urls` holding `/api/documents/{document_id}/screenshot/{viewport}` for each viewport that has a screenshot key. The document's `scrape_meta` SHALL carry `rescan` `{state, latest_document_id, checked_at}`, derived on read and never stored, keeping the scraper's own `scrape_meta` keys. "The same page" is a document with the same `source_id` (null matches null) and the same `canonical_url`, else `url`, fetched strictly later. `state` SHALL be `removed` if a `job_errors` row for the page (same `source_id`, `url` equal to the page key or the document's `url`, `reason` `http_error`, `detail` `HTTP 404` or `HTTP 410`) is newer than the last fetch of the page, or if the newest later fetch has `http_status` 404 or 410; else `changed` if the newest later fetch has a different `content_hash`; else `current`. `latest_document_id` SHALL be the newest later fetch's id, or null when there is none or the state comes from a job error; `checked_at` SHALL be the time of the observation the state comes from.

#### Scenario: Document with two screenshots
- **WHEN** the finding's document has `screenshots` for `desktop` and `mobile` only
- **THEN** `screenshot_urls` has exactly the keys `desktop` and `mobile`, each pointing to the screenshot route

#### Scenario: Document without screenshots
- **WHEN** the finding's document has no `screenshots`
- **THEN** `screenshot_urls` is an empty object and `document` is still present

#### Scenario: Page not fetched again
- **WHEN** no later document of the same page exists
- **THEN** `document.scrape_meta.rescan` is `{state: "current", latest_document_id: null, checked_at: <the document's fetched_at>}`

#### Scenario: Re-scan found new text
- **WHEN** a later fetch of the same page stored a document with a different `content_hash`
- **THEN** the old finding's `rescan.state` is `changed` with `latest_document_id` the new document's id, and the new document's finding has `rescan.state` `current`

#### Scenario: Page gone on re-scan
- **WHEN** the newest later fetch has `http_status` 404 or 410, or a `job_errors` row `HTTP 404`/`HTTP 410` for the page is newer than the last fetch
- **THEN** `rescan.state` is `removed`

#### Scenario: Unrelated rows do not count
- **WHEN** the later document is another page or another source, or the job error is older than the last fetch, is not a 404/410, or names another source
- **THEN** they do not change `rescan.state`
