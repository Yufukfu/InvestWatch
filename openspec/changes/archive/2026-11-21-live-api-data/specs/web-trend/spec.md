## MODIFIED Requirements

### Requirement: Trend chart
The dashboard SHALL show the number of findings per time bucket for each module (`M1`, `M2`, `M3`) from `GET /stats/trend` (integration plan §5), drawn with Recharts, as a presentational component that takes its data as props and does not fetch. Series SHALL differ by colour and by dash pattern on the lines and on the legend swatches.

#### Scenario: Chart from mocks
- **WHEN** the backend answers `GET /stats/trend` with `contracts/mocks/trend.json`
- **THEN** the trend section shows one series each for M1, M2 and M3 with a legend naming them and their totals, built from those points

#### Scenario: Values are not colour-only
- **WHEN** the chart renders
- **THEN** M2 and M3 lines and legend swatches carry different dash patterns, M1 is solid, and the image's accessible name states the totals per module

#### Scenario: Chart component is pure
- **WHEN** `TrendChart` is rendered in a test with `points` props and no store provider
- **THEN** it renders the series without error and makes no network request

### Requirement: Bucket switch
The trend section SHALL let the user choose hourly or daily buckets with keyboard-operable controls in a labelled group, request the trend with that bucket, draw the points the backend returns for that bucket without re-aggregating them, and never show the previous bucket's data while the new one loads.

#### Scenario: Default bucket
- **WHEN** the trend section first renders
- **THEN** `Godzina` is pressed and the request carries `bucket=hour`

#### Scenario: Switch to days
- **WHEN** the user activates `Dzień`
- **THEN** `Dzień` is pressed and a new request is sent with `bucket=day`

#### Scenario: No stale data after a switch
- **WHEN** the user activates `Dzień` and the day response has not arrived yet
- **THEN** the section shows the loading text and not the hourly totals

#### Scenario: Day data in the mock
- **WHEN** the backend (the contract mock server or the api) answers `bucket=day` with a set of day points
- **THEN** the chart's table shows exactly those points and counts, one row per point
