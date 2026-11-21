## Why

The dashboard has a findings table and summary cards but no view of how detections develop over time, which the challenge and `web/CLAUDE.md` ("Done": filters, trend, status change, alerts) require. [ADR 0203](../../../.docs/decisions/0203-dashboard-charts-recharts.md) chose Recharts as the one chart library but nothing is installed yet. This change installs it and builds the trend chart, the first chart, so the calibration curve can reuse the same setup later.

## What Changes

- Add `recharts` to `web/` (MIT, with the matching `react-is` peer), run `npm audit`, and measure the production bundle size with `vite build` (ADR 0203 asks the install PR to do this).
- New `trend` feature in `web/src/features/trend/` following [ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md): `data/useTrend.ts` (the only file importing the generated `useGetStatsTrendQuery`), presentational `components/TrendChart.tsx` (props in, JSX out), and `TrendPage.tsx` joining them.
- The chart shows findings per bucket for M1, M2 and M3 from `GET /stats/trend`, with an hour/day switch, a legend, and loading, empty and error states. It runs on the contract mock (`mocks/trend.json`) with no component change when the live `api` replaces it.
- Mount the trend section in `App.tsx` between the summary cards and the findings table.
- Docs: `.docs/STATUS.md` row and `web/README.md`; the jsdom/`ResizeObserver` finding that ADR 0203 lists as unverified is recorded in the STATUS row and the AI log (the ADR is not edited in place).

## Capabilities

### New Capabilities
- `web-trend`: trend chart of findings over time per module.

### Modified Capabilities
- none

## Impact

- Owner: B (`web/`). Touches no contract, REST route or event; it only consumes `GET /stats/trend` as already defined in `contracts/openapi.yaml`.
- New dependencies: `recharts` and `react-is` (runtime), recorded by ADR 0203; no new ADR needed.
- Out of scope: the calibration curve, the `module` / `risk_level` / date-range filters on the trend (the API supports them; a follow-up change can add controls), URL search-param state for the bucket (the follow-up that adds filters does this together), moving the existing `FindingsTable`, `SummaryCards` and `HealthBadge` to the ADR 0204 layout (separate refactor change).
