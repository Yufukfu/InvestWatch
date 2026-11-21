# Proposal

## Why

Review of PR #14 (hen68) found that the trend chart puts Recharts' keyboard layer inside a `role="img"` with only the three totals as text, that the "colour plus dash pattern", "no stale data after a switch" and "local hour ticks" claims are not pinned by tests, that the `Dzień` view is never drawn with day data (the mock always returns hourly points), and that `.docs/integration-plan.md` §5 documents `/stats/trend` as a bare array while OpenAPI returns `{bucket, points}`.

## What Changes

- Chart accessibility: `accessibilityLayer={false}`, the plot stays one `role="img"`, and a collapsible table (bucket by M1/M2/M3) is the text alternative. Totals are shown in the legend.
- Time labels: hour ticks in local time with the date on the tick at local midnight, hour tooltip with the date, day ticks as UTC dates with a visible "Dni liczone w czasie UTC." note.
- Mock: the default MSW handler aggregates the hourly contract mock into UTC days for `bucket=day`, so the demo and the tests draw real day data.
- Tests: dash patterns on lines and legend swatches, no stale hourly totals under `Dzień` with a delayed day response, local hour ticks, UTC day ticks in two timezones, the page with the day mock.
- Nits: `role="status"` on loading, a labelled `role="group"` around the bucket buttons, tooltip without animation, test names, the no-op `overflow-x` and the redundant smoke test removed.
- `TrendBucket` and `TrendPoint` move to `features/trend/model.ts`, so the data hook no longer imports from a component (ADR 0204 rule).
- `TrendPage` is lazy-loaded from `App.tsx`, so Recharts is a separate chunk.
- Docs: `.docs/integration-plan.md` §5 matches OpenAPI; ADR 0203 gets a short note pointing at the measurement.

**Out of scope:** module display names (the dashboard shows the codes `M1`/`M2`/`M3` everywhere, e.g. the findings table), trend filters, contract mocks in `contracts/` (owner C). Owner B.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-trend`: text alternative and dash patterns, time labels, day data in the mock, no stale data after a switch.

## Impact

- Code: `web/src/features/trend/**`, `web/src/mocks/handlers.ts`, `web/src/App.tsx`, `web/src/styles.css`.
- Docs: `.docs/integration-plan.md` §5, ADR 0203 note, `.docs/STATUS.md`, AI log row. No dependency added; no contract change.
