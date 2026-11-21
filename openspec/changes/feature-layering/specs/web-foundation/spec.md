# Spec Delta

## ADDED Requirements

### Requirement: Presentational feature components
Dashboard feature components SHALL render only from their props, with no store, network call or generated-client access of their own. Each feature SHALL get its data through one data hook that returns plain values and callbacks.

#### Scenario: Component renders from props alone
- **WHEN** a feature component is rendered in a test with props and no store provider
- **THEN** it renders the values it was given, including its loading, error and empty states

#### Scenario: Findings table error state from props
- **WHEN** the findings table is rendered with an error flag and no rows
- **THEN** it shows an alert reading "Nie udało się pobrać zgłoszeń." and no table

#### Scenario: Data hook against the API
- **WHEN** a feature's data hook runs against the mock handlers
- **THEN** it returns the rows or values the component needs, taken from the contract mock for that endpoint

#### Scenario: Data hook when the API is unreachable
- **WHEN** a feature's data hook runs and the API request fails
- **THEN** it reports an error state instead of throwing, and the page shows the error message

### Requirement: Layering enforced by lint
`npm run lint` SHALL fail when a presentational feature component imports the API client, a data hook or the store.

#### Scenario: Component imports the API client
- **WHEN** a file under `src/features/*/components/` imports from `src/api/`
- **THEN** `npm run lint` exits non-zero and names the restricted import

#### Scenario: Data hook imports the API client
- **WHEN** a file under `src/features/*/data/` imports from `src/api/`
- **THEN** `npm run lint` does not report it
