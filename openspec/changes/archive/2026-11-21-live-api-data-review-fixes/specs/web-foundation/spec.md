## MODIFIED Requirements

### Requirement: Presentational feature components
Dashboard feature components SHALL render only from their props, with no store, network call or generated-client access of their own. Each feature SHALL get its data through one data hook that returns plain values and callbacks.

#### Scenario: Component renders from props alone
- **WHEN** a feature component is rendered in a test with props and no store provider
- **THEN** it renders the values it was given, including its loading, error and empty states

#### Scenario: Findings table error state from props
- **WHEN** the findings table is rendered with an error flag and no rows
- **THEN** it shows an alert reading "Nie udało się pobrać zgłoszeń." and no table

#### Scenario: Data hook against the API
- **WHEN** a feature's data hook runs in a test against the Vitest network fake
- **THEN** it returns the rows or values the component needs, taken from the contract mock for that endpoint

#### Scenario: Data hook when the API is unreachable
- **WHEN** a feature's data hook runs and the API request fails
- **THEN** it does not throw: health and findings report an error state that the component shows, and the summary reports no data so its cards are not rendered (unchanged behaviour)

### Requirement: Data from the backend
The running dashboard SHALL get all data from the backend at `VITE_API_BASE_URL` (default `/api`) through the generated client, with no in-browser fake backend in any build. A fake network SHALL exist only in the Vitest setup, serving the contract mocks unchanged.

#### Scenario: Findings from the backend
- **WHEN** the app runs against a backend that answers `GET /api/findings` with `contracts/mocks/findings.json`
- **THEN** the findings table shows those titles as plain text

#### Scenario: No fake backend in app code
- **WHEN** the shipped files are checked: sources under `web/src/` outside `src/test/` and test files, `web/public/`, the root `*.html`, `*.js`, `*.mjs`, `*.cjs` and `.env*` files
- **THEN** none imports `msw`, imports from `src/test/`, registers a service worker or mentions `useMocks` or `VITE_USE_MOCKS`, and `web/public/` has no `mockServiceWorker.js`

#### Scenario: No browser worker anywhere in src
- **WHEN** every file under `web/src/`, tests and test support included, is checked
- **THEN** none references `msw/browser` or `setupWorker`

#### Scenario: API down
- **WHEN** the API is unreachable
- **THEN** the health badge shows "Brak połączenia z API" and the table shows an error message instead of crashing

#### Scenario: System reported down
- **WHEN** the API answers `/health` with `status: down`
- **THEN** the health badge shows "System nie działa", not the unreachable message
