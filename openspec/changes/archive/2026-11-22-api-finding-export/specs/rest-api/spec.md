## ADDED Requirements

### Requirement: Evidence pack of a finding
`GET /api/findings/{id}/export` SHALL be read-only and SHALL return, for `format=json` (the default), a JSON object with `export_version` `"1"`, `generated_at`, `finding` (the finding as on `GET /api/findings/{id}`, with `risk_level`), `document` and `screenshot_urls` (as on the detail), `failed_rules` (the finding's rules with `result` `fail`, in stored order) and `raw`. `raw` SHALL hold the object at the document's `html_object_key` (never a key from the request): `available` true, `sha256` and `size_bytes` of the whole object, and `html` with at most the first 2 000 000 bytes decoded as UTF-8 (`truncated` true when cut). When there is no key, no object or the object store fails, `raw.available` SHALL be false with `unavailable_reason` `no_key`, `not_found` or `store_down`, and the rest of the pack SHALL still be returned. For `format=html` the route SHALL return the same content as a printable page in Polish, with every stored value HTML-escaped, links only for `http`/`https` URLs, and a `Content-Security-Policy` that allows no scripts.

#### Scenario: JSON case file
- **WHEN** a finding's document has a raw HTML object and a desktop screenshot and a client calls `GET /api/findings/{id}/export`
- **THEN** the response is 200 JSON that validates against `contracts/openapi.yaml` and holds the document's `url`, `content_hash` and `fetched_at`, the raw HTML with its SHA-256, the screenshot URL and only the failed rules with their `legal_basis` and `evidence`

#### Scenario: Printable page
- **WHEN** a client calls `GET /api/findings/{id}/export?format=html`
- **THEN** the response is 200 `text/html` showing the same facts, and scraped text such as `<script>` appears only escaped

#### Scenario: Object store down
- **WHEN** the object store fails while the export is built
- **THEN** the response is 200 with `raw.available` false and `raw.unavailable_reason` `store_down`

#### Scenario: Unknown finding
- **WHEN** a client calls `GET /api/findings/{id}/export` with a well-formed UUID that has no row, in either format
- **THEN** the response is 404 with an error body

#### Scenario: Unknown format
- **WHEN** a client calls `GET /api/findings/{id}/export?format=pdf`
- **THEN** the response is 422 naming `format`
