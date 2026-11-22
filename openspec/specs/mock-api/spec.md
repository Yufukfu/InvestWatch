# mock-api Specification

## Purpose
A contract-conformant stand-in for the InvestWatch REST API and Socket.IO events, backed by `contracts/mocks/`, so the dashboard can be developed and demoed without the other services. Lives in `contracts/mock-server/`.
## Requirements
### Requirement: Serve the contract REST routes from mock data
The mock server SHALL expose every path of `contracts/openapi.yaml` under the `/api` prefix on a configurable port (default `8000`), and every JSON response SHALL validate against the schema referenced by that path in `contracts/openapi.yaml` and `contracts/schemas/`. Data SHALL come from the files in `contracts/mocks/` (mock-to-endpoint table in `contracts/README.md`); the contracts themselves are defined in `.docs/integration-plan.md` §4-§5 and are not restated here.

#### Scenario: List findings
- **WHEN** a client sends `GET /api/findings`
- **THEN** the server responds 200 with `items`, `total`, `page` and `page_size`, every item validates against `finding.schema.json` and includes a `risk_level`

#### Scenario: Finding detail
- **WHEN** a client sends `GET /api/findings/{id}` for an id present in the mocks
- **THEN** the server responds 200 with the finding plus its `document` (valid against `scraped-document.schema.json`) and `screenshot_urls`

#### Scenario: Unknown finding
- **WHEN** a client sends `GET /api/findings/{id}` for an id not present in the mocks
- **THEN** the server responds 404 with a body `{ "error": ... }`

#### Scenario: Malformed id
- **WHEN** a client sends `GET /api/findings/not-a-uuid`
- **THEN** the server responds 422 and does not crash

#### Scenario: Stats, calibration, settings, sources and health
- **WHEN** a client calls `GET /api/stats/summary`, `GET /api/stats/trend`, `GET /api/calibration?module=M2`, `GET /api/settings/thresholds`, `GET /api/sources` or `GET /api/health`
- **THEN** each responds 200 with a body that matches the response schema of that path in `contracts/openapi.yaml`

#### Scenario: Calibration without module
- **WHEN** a client sends `GET /api/calibration` without the required `module` parameter
- **THEN** the server responds 422

#### Scenario: Screenshot placeholder
- **WHEN** a client sends `GET /api/documents/{id}/screenshot/desktop` for a document that has screenshots in the mocks
- **THEN** the server responds 200 with `Content-Type: image/png`
- **AND WHEN** the document has no screenshots or does not exist
- **THEN** the server responds 404

### Requirement: Filter, sort and paginate findings
`GET /api/findings` SHALL apply the query parameters defined in `contracts/openapi.yaml` (`module`, `status` as a comma-separated list, `platform`, `source_id`, `risk_level`, `score_min`, `date_from`, `date_to`, `q`, `sort`, `page`, `page_size`), and `total` SHALL count all matches before pagination.

#### Scenario: Filter by module and status
- **WHEN** a client sends `GET /api/findings?module=M2&status=new,in_review`
- **THEN** every returned item has `module` `M2` and a status of `new` or `in_review`, and `total` equals the number of such findings in the mocks

#### Scenario: Full-text search
- **WHEN** a client sends `GET /api/findings?q=inwestor_jan`
- **THEN** only findings whose title, excerpt, firm name, advertiser name or advertiser handle contain that text (case-insensitive) are returned, as `contracts/openapi.yaml` describes `q`; the summary is not searched

#### Scenario: Pagination
- **WHEN** a client sends `GET /api/findings?page=2&page_size=2`
- **THEN** the response contains at most 2 items, `page` is 2, and the items are the third and fourth of the sorted result

#### Scenario: Invalid filter value
- **WHEN** a client sends `GET /api/findings?module=M9` or `page_size=0`
- **THEN** the server responds 422

#### Scenario: No matches
- **WHEN** the filters match no finding
- **THEN** the server responds 200 with an empty `items` list and `total` 0

### Requirement: Keep write operations in memory
`PATCH /api/findings/{id}`, `PUT /api/settings/thresholds`, `POST /api/sources`, `PATCH /api/sources/{id}` and `POST /api/scans` SHALL change an in-memory copy of the mock data so later reads reflect them, without writing to `contracts/mocks/`. Restarting the server or calling `POST /__mock/reset` SHALL restore the original mock data.

#### Scenario: Change finding status
- **WHEN** a client sends `PATCH /api/findings/{id}` with `{ "status": "confirmed" }`
- **THEN** the response is the updated finding, a following `GET /api/findings/{id}` returns status `confirmed`, and `updated_at` is later than before

#### Scenario: Invalid status
- **WHEN** a client sends `PATCH /api/findings/{id}` with `{ "status": "approved" }` or an empty body
- **THEN** the server responds 422 and the finding is unchanged

#### Scenario: Threshold change recomputes risk levels
- **WHEN** a client sends `PUT /api/settings/thresholds` with `{ "M1": 0.6, "M2": 0.9, "M3": 0.7 }`
- **THEN** a following `GET /api/findings?module=M2` returns `risk_level` derived from the new M2 threshold (high when `score` >= 0.9, medium when >= 0.7, otherwise low), and `GET /api/calibration?module=M2` reports `current_threshold` 0.9

#### Scenario: Threshold out of range
- **WHEN** a client sends `PUT /api/settings/thresholds` with a value above 1 or a missing module
- **THEN** the server responds 422 and the thresholds are unchanged

#### Scenario: Add and edit a source
- **WHEN** a client sends `POST /api/sources` with a valid source body
- **THEN** the server responds 201 with a source that has a new UUID and validates against `source.schema.json`, and it appears in `GET /api/sources`
- **AND WHEN** the client then sends `PATCH /api/sources/{id}` with `{ "active": false }`
- **THEN** the returned source has `active` false

#### Scenario: Scan an unknown source
- **WHEN** a client sends `POST /api/scans` with a `source_id` that does not exist
- **THEN** the server responds 404 and emits no event

#### Scenario: Reset
- **WHEN** a client sends `POST /__mock/reset` after any write
- **THEN** all reads return the original mock data again

### Requirement: Emit contract events over Socket.IO
The server SHALL accept Socket.IO clients on the namespace `/events` and emit events whose name is the event `type` and whose payload is the event `data`, both valid against `contracts/schemas/events.schema.json` (contract in `.docs/integration-plan.md` §6).

#### Scenario: Status change event
- **WHEN** a finding status is changed through `PATCH /api/findings/{id}`
- **THEN** every connected client receives `finding.updated` with `{ id, status }`

#### Scenario: Manual scan events
- **WHEN** a client sends `POST /api/scans` for an existing source
- **THEN** the server responds 202, connected clients receive `scan.started` and then, after a short configurable delay, `scan.finished` with the same `source_id`

#### Scenario: Periodic replay of findings
- **WHEN** replay is enabled (default on, interval configurable, for example every 10 s) and a client is connected
- **THEN** the server periodically adds a new finding derived from a mock finding (new UUID, current `detected_at`), so it also appears in `GET /api/findings`, and emits `finding.created`
- **AND WHEN** that finding's `score` is greater than or equal to its module's current threshold
- **THEN** the server also emits `finding.high_risk` with the same payload

#### Scenario: Replay disabled
- **WHEN** the server is started with replay disabled
- **THEN** no `finding.created` events are emitted unless triggered through `POST /__mock/emit`

#### Scenario: Client disconnects
- **WHEN** a client disconnects while replay is running
- **THEN** the server keeps running and other clients keep receiving events

### Requirement: Be usable from the dashboard during development
The server SHALL allow cross-origin requests from configurable origins (default the local dev origins), SHALL log in JSON to stdout without printing request bodies, and SHALL fail at start-up with a clear message when a mock file is missing or does not validate against its schema.

#### Scenario: CORS for the dev server
- **WHEN** the dashboard dev server on an allowed origin calls `GET /api/findings`
- **THEN** the response carries the matching `Access-Control-Allow-Origin` header

#### Scenario: Broken mock data
- **WHEN** the server starts and `contracts/mocks/findings.json` is missing or contains an item that fails `finding.schema.json`
- **THEN** the process exits with a non-zero code and an error naming the file, instead of serving invalid data

### Requirement: Filter mock findings by document
The mock server's `GET /api/findings` SHALL accept an optional `document_id` (UUID), as `contracts/openapi.yaml` defines it, and return only findings of that document, combined (AND) with the other filters, sort and pagination, with `total` counting all matches before pagination. A malformed value SHALL get 422.

#### Scenario: Document with two findings
- **WHEN** a client sends `GET /api/findings?document_id=<the mock document with M1 and M3 findings>`
- **THEN** the response holds exactly its M1 and M3 findings and `total` is 2

#### Scenario: Document and module together
- **WHEN** a client sends the same request with `module=M1`
- **THEN** only the M1 finding is returned and `total` is 1

#### Scenario: Malformed or unknown document id
- **WHEN** a client sends `document_id=not-a-uuid`, or a UUID no mock finding references
- **THEN** the server responds 422 for the first and 200 with empty `items` and `total` 0 for the second

### Requirement: Mocks include a document with several findings
The generated mocks SHALL contain at least one document that has findings from two modules (M1 and M3), each with its own `id`, so the dashboard can show several findings for one post. Findings SHALL stay unique per `(document_id, module)`.

#### Scenario: M1 and M3 on one post
- **WHEN** `python contracts/mocks/generate_mocks.py` runs
- **THEN** `findings.json` has exactly one `document_id` shared by two findings, one with `module` M1 and one with M3, and `python contracts/validate.py` exits 0

### Requirement: Serve the finding evidence pack
The mock server SHALL serve `GET /api/findings/{id}/export` as in `contracts/openapi.yaml` 1.2.0: a JSON pack for `format=json` (the default) and a printable HTML page with the same content for `format=html`. An unknown id SHALL return 404 in both formats and a malformed id or `format` SHALL return 422.

#### Scenario: JSON pack of a mock finding
- **WHEN** the dashboard calls `GET /api/findings/{id}/export` for any mock finding
- **THEN** the response is 200, validates against `contracts/openapi.yaml` and matches that finding's detail
- **AND** the pack's `finding`, `document` and `screenshot_urls` SHALL equal the mock `GET /api/findings/{id}` body, and its `failed_rules` SHALL be the finding's rules with `result` `fail`
- **AND** `raw.available` SHALL be false, with `unavailable_reason` `not_found` when the mock document has an `html_object_key` and `no_key` otherwise

#### Scenario: Printable page
- **WHEN** the dashboard opens `GET /api/findings/{id}/export?format=html`
- **THEN** the response is 200 `text/html` with a CSP starting `default-src 'none'`
- **AND** every value on the page SHALL be HTML-escaped and the `Content-Security-Policy` SHALL allow no scripts

#### Scenario: Unknown finding
- **WHEN** a client calls the export with a well-formed UUID that is not a mock finding
- **THEN** the response is 404 with an error body

