## ADDED Requirements

### Requirement: Serve bulk status, report export and M2 coverage
The mock server SHALL serve `POST /api/findings/bulk-status`, `GET /api/findings/export` and `m2_coverage` in `GET /api/stats/summary` as contract 1.3.0 defines them, on its in-memory data. The bulk change SHALL update the stored findings and emit one `finding.updated` event per updated finding. The export SHALL apply the same filters and sort as the mock's `GET /api/findings`. The coverage SHALL count the stored M2 findings.

#### Scenario: Bulk change in mock mode
- **WHEN** the dashboard sends a bulk change for two mock findings and one unknown id
- **THEN** the response validates against `contracts/openapi.yaml`, both findings have the new status on `GET /api/findings/{id}`, and two `finding.updated` events are emitted

#### Scenario: Export in mock mode
- **WHEN** the dashboard calls `GET /api/findings/export?module=M2`
- **THEN** the response is a CSV whose rows are the mock M2 findings

#### Scenario: Bad bulk body in mock mode
- **WHEN** the dashboard sends a bulk change with a repeated id
- **THEN** the response is 422 and no finding changes
