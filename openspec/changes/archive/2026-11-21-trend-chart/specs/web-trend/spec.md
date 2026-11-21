## ADDED Requirements

### Requirement: Trend chart
The dashboard SHALL show the number of findings per time bucket for each module (`M1`, `M2`, `M3`) from `GET /stats/trend` (integration plan §5), drawn with Recharts, as a presentational component that takes its data as props and does not fetch.

#### Scenario: Chart from mocks
- **WHEN** the app runs against the mock handlers
- **THEN** the trend section shows one series each for M1, M2 and M3 with a legend naming them, built from the points of `contracts/mocks/trend.json`

#### Scenario: Values are not colour-only
- **WHEN** the chart renders
- **THEN** each series is identified by a legend label and its container has an accessible name that states the totals per module

#### Scenario: Chart component is pure
- **WHEN** `TrendChart` is rendered in a test with `points` props and no store provider
- **THEN** it renders the series without error and makes no network request

### Requirement: Bucket switch
The trend section SHALL let the user choose hourly or daily buckets with keyboard-operable controls, and request the trend with that bucket.

#### Scenario: Default bucket
- **WHEN** the trend section first renders
- **THEN** `Godzina` is pressed and the request carries `bucket=hour`

#### Scenario: Switch to days
- **WHEN** the user activates `Dzień`
- **THEN** `Dzień` is pressed and a new request is sent with `bucket=day`

### Requirement: Trend states
The trend section SHALL show a text state for loading, error and no data instead of a broken or empty chart.

#### Scenario: Loading
- **WHEN** the trend request is pending
- **THEN** the section shows "Ładowanie wykresu…"

#### Scenario: API error
- **WHEN** `GET /stats/trend` fails or the API is unreachable
- **THEN** the section shows "Nie udało się pobrać danych trendu." and the rest of the page keeps working

#### Scenario: No data
- **WHEN** the response has no points, or every count is zero
- **THEN** the section shows "Brak danych w wybranym okresie." and no chart

#### Scenario: Malformed point
- **WHEN** a point has a missing module count
- **THEN** that count is treated as 0 and the chart still renders
