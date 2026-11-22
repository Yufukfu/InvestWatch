## ADDED Requirements

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
