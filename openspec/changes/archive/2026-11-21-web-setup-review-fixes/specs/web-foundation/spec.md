## MODIFIED Requirements

### Requirement: Mock mode
The dashboard SHALL render contract mock data without the `api` service, with no change to components.

#### Scenario: Findings from mocks
- **WHEN** the app runs against the mock handlers
- **THEN** the findings table shows the titles from `contracts/mocks/findings.json` as plain text

#### Scenario: API down
- **WHEN** the API is unreachable
- **THEN** the health badge shows "Brak połączenia z API" and the table shows an error message instead of crashing

#### Scenario: System reported down
- **WHEN** the API answers `/health` with `status: down`
- **THEN** the health badge shows "System nie działa", not the unreachable message
