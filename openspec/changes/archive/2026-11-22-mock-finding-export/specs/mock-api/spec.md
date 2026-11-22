## ADDED Requirements

### Requirement: Serve the finding evidence pack
The mock server SHALL serve `GET /api/findings/{id}/export` as in `contracts/openapi.yaml` 1.2.0: for `format=json` (the default) a pack whose `finding`, `document` and `screenshot_urls` equal the mock `GET /api/findings/{id}` body, whose `failed_rules` are the finding's rules with `result` `fail`, and whose `raw.available` is false with `unavailable_reason` `not_found` when the mock document has an `html_object_key` and `no_key` otherwise; for `format=html` the same content as a printable page with every value HTML-escaped and a `Content-Security-Policy` that allows no scripts. An unknown id SHALL return 404 in both formats and a malformed id or `format` SHALL return 422.

#### Scenario: JSON pack of a mock finding
- **WHEN** the dashboard calls `GET /api/findings/{id}/export` for any mock finding
- **THEN** the response is 200, validates against `contracts/openapi.yaml` and matches that finding's detail

#### Scenario: Printable page
- **WHEN** the dashboard opens `GET /api/findings/{id}/export?format=html`
- **THEN** the response is 200 `text/html` with a CSP starting `default-src 'none'`

#### Scenario: Unknown finding
- **WHEN** a client calls the export with a well-formed UUID that is not a mock finding
- **THEN** the response is 404 with an error body
