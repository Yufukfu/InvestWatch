## ADDED Requirements

### Requirement: Findings of one document
`GET /api/findings` SHALL accept an optional `document_id` (UUID) and then return only findings whose `document_id` equals it. It SHALL combine with every other filter (AND), `sort` and pagination as in `Findings list filters, sort and pagination`, with `total` counting the document's matching findings. A request without `document_id` SHALL behave as before.

#### Scenario: Every finding of a document
- **WHEN** a document has an M1 and an M3 finding and a client calls `GET /api/findings?document_id=<that id>`
- **THEN** the response holds exactly those two findings and `total` is 2

#### Scenario: Combined with the module filter
- **WHEN** a client calls `GET /api/findings?document_id=<that id>&module=M3`
- **THEN** only the M3 finding of that document is returned and `total` is 1

#### Scenario: Combined with pagination
- **WHEN** a client calls `GET /api/findings?document_id=<that id>&page=2&page_size=1&sort=score`
- **THEN** `items` holds the second finding of that document by ascending score, `total` is 2, `page` is 2 and `page_size` is 1

#### Scenario: Unknown document
- **WHEN** a client calls `GET /api/findings?document_id=<a UUID with no findings>`
- **THEN** the response is 200 with an empty `items` list and `total` 0

#### Scenario: Malformed document id
- **WHEN** a client calls `GET /api/findings?document_id=not-a-uuid`
- **THEN** the response is 422 naming `document_id`
