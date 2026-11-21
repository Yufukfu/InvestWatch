## MODIFIED Requirements

### Requirement: Layering enforced by lint
`npm run lint` SHALL fail when a presentational feature component, at any folder depth under `src/features/*/components/`, imports the API client, a data hook (relative path through a `data` folder), a page component, the store, `react-redux`, `@reduxjs/toolkit` or `socket.io-client`, including their subpaths and imports written with a file extension. `npm test` SHALL fail on the same violations in the real components, so a CI that only runs the tests still enforces the layering.

#### Scenario: Component imports the API client
- **WHEN** a file under `src/features/*/components/` imports from `src/api/`
- **THEN** `npm run lint` exits non-zero and names the restricted import

#### Scenario: Nested component reaches another feature's data hook
- **WHEN** a file in `src/features/*/components/sub/` imports `../../../health/data/useHealth`
- **THEN** `npm run lint` exits non-zero

#### Scenario: Page imported with an extension or a package imported by subpath
- **WHEN** a component imports `../DemoPage.tsx` or `react-redux/es/x`
- **THEN** `npm run lint` exits non-zero

#### Scenario: Data hook imports the API client
- **WHEN** a file under `src/features/*/data/` imports from `src/api/`
- **THEN** `npm run lint` does not report it

#### Scenario: Real components are checked by the tests
- **WHEN** a real component under `src/features/*/components/` imports `src/api/`
- **THEN** `npm test` fails
