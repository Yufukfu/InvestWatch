## MODIFIED Requirements

### Requirement: Finding detail with its document
`GET /api/findings/{id}` SHALL return the finding with `risk_level`, its `document` in the `ScrapedDocument` shape, and `screenshot_urls` holding `/api/documents/{document_id}/screenshot/{viewport}` for each viewport that has a screenshot key. The document's `scrape_meta` SHALL carry `rescan` `{state, latest_document_id, checked_at}`, derived on read and never stored, keeping the scraper's own `scrape_meta` keys.

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
- **AND** "the same page" SHALL be a document with the same `source_id` (null matches null) and the same `canonical_url`, else `url`, fetched strictly later
- **AND** `state` SHALL be `changed` if the newest later fetch has a different `content_hash`, else `current` (unless it is `removed`); `latest_document_id` SHALL be the newest later fetch's id, or null when there is none

#### Scenario: Page gone on re-scan
- **WHEN** the newest later fetch has `http_status` 404 or 410, or a `job_errors` row `HTTP 404`/`HTTP 410` for the page is newer than the last fetch
- **THEN** `rescan.state` is `removed`
- **AND** `state` SHALL be `removed` if a `job_errors` row for the page (same `source_id`, `url` equal to the page key or the document's `url`, `reason` `http_error`, `detail` `HTTP 404` or `HTTP 410`) is newer than the last fetch of the page, or if the newest later fetch has `http_status` 404 or 410
- **AND** `latest_document_id` SHALL be null when the state comes from a job error, and `checked_at` SHALL be the time of the observation the state comes from

#### Scenario: Unrelated rows do not count
- **WHEN** the later document is another page or another source, or the job error is older than the last fetch, is not a 404/410, or names another source
- **THEN** they do not change `rescan.state`

#### Scenario: Page returns to earlier text
- **WHEN** a re-fetch of the page returns text the scraper already stored, so it stores no new row
- **THEN** the page keeps the state of the last new text: the state describes the page since its last stored version

### Requirement: Evidence pack of a finding
`GET /api/findings/{id}/export` SHALL be read-only and SHALL return, for `format=json` (the default), a JSON object with `export_version` `"1"`, `generated_at`, `finding` (the finding as on `GET /api/findings/{id}`, with `risk_level`), `document` and `screenshot_urls` (as on the detail), `failed_rules` (the finding's rules with `result` `fail`, in stored order) and `raw`. For `format=html` the route SHALL return the same content as a printable page in Polish.

#### Scenario: JSON case file
- **WHEN** a finding's document has a raw HTML object and a desktop screenshot and a client calls `GET /api/findings/{id}/export`
- **THEN** the response is 200 JSON that validates against `contracts/openapi.yaml` and holds the document's `url`, `content_hash` and `fetched_at`, the raw HTML with its SHA-256, the screenshot URL and only the failed rules with their `legal_basis` and `evidence`
- **AND** `raw` SHALL hold the object at the document's `html_object_key` (never a key from the request): `available` true, `sha256` and `size_bytes` of the whole object, and `html` with at most the first 2 000 000 bytes decoded as UTF-8 (`truncated` true when cut)

#### Scenario: Printable page
- **WHEN** a client calls `GET /api/findings/{id}/export?format=html`
- **THEN** the response is 200 `text/html` showing the same facts, and scraped text such as `<script>` appears only escaped
- **AND** every stored value SHALL be HTML-escaped, links SHALL be rendered only for `http`/`https` URLs, and the `Content-Security-Policy` SHALL allow no scripts

#### Scenario: Object store down
- **WHEN** the object store fails while the export is built
- **THEN** the response is 200 with `raw.available` false and `raw.unavailable_reason` `store_down`
- **AND** when there is no key, no object or the object store fails, `raw.available` SHALL be false with `unavailable_reason` `no_key`, `not_found` or `store_down`, and the rest of the pack SHALL still be returned

#### Scenario: Unknown finding
- **WHEN** a client calls `GET /api/findings/{id}/export` with a well-formed UUID that has no row, in either format
- **THEN** the response is 404 with an error body

#### Scenario: Unknown format
- **WHEN** a client calls `GET /api/findings/{id}/export?format=pdf`
- **THEN** the response is 422 naming `format`
