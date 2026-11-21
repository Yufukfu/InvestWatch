# web-trend Specification

## Purpose

The trend view of the dashboard (`web/`, owner B): findings per time bucket and module from `GET /stats/trend`, drawn with Recharts as a presentational chart, with an hour/day switch and text states for loading, error and no data.

## Requirements

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

### Requirement: Trend states
The trend section SHALL show a text state for loading, error and no data instead of a broken or empty chart. The loading text SHALL be announced as a status.

#### Scenario: Loading
- **WHEN** the trend request is pending
- **THEN** the section shows "Ładowanie wykresu…" with `role="status"`

#### Scenario: API error
- **WHEN** `GET /stats/trend` fails or the API is unreachable
- **THEN** the section shows "Nie udało się pobrać danych trendu." and the rest of the page keeps working

#### Scenario: Trend chunk fails to load
- **WHEN** the lazy-loaded trend code cannot be loaded
- **THEN** the section shows "Nie udało się pobrać danych trendu." and the summary and findings keep working

#### Scenario: No data
- **WHEN** the response has no points, or every count is zero
- **THEN** the section shows "Brak danych w wybranym okresie." and no chart

#### Scenario: Malformed point
- **WHEN** a point has a missing module count
- **THEN** that count is treated as 0 and the chart still renders

### Requirement: Chart text alternative
The plot SHALL be one image with the totals per module as its accessible name and no interactive content inside it, and a table of every bucket by module SHALL be available as its text alternative.

#### Scenario: Text alternative
- **WHEN** the chart renders
- **THEN** a table lists every bucket with its M1, M2 and M3 counts, and the image contains no focusable element

### Requirement: Time labels
Hour buckets SHALL be labelled in the viewer's local time, with the date in the tooltip, in the data table and on the tick at local midnight whenever that tick is drawn (Recharts may skip ticks to avoid overlap). Day buckets SHALL be labelled with their UTC date, and the day view SHALL say that days are UTC.

#### Scenario: Hour ticks
- **WHEN** the hourly view renders in a browser in `Asia/Tokyo`
- **THEN** a point at `2026-11-20T17:00:00Z` is labelled `02:00` and a point at `2026-11-20T15:00:00Z` is labelled with the date `21 lis`

#### Scenario: Hour tooltip
- **WHEN** the tooltip opens on the point `2026-11-20T18:00:00Z` in `Asia/Tokyo`
- **THEN** its label reads `21 lis, 03:00`

#### Scenario: Day ticks
- **WHEN** the daily view renders in a browser in `America/Los_Angeles` or `Asia/Tokyo`
- **THEN** a point at `2026-11-20T00:00:00Z` is labelled `20 lis` and the section shows "Dni liczone w czasie UTC."
