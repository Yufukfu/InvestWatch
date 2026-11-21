# 0203. Dashboard charts: Recharts

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from the team's choice (Recharts); accepted by: pending approval of the PR

## Context

The dashboard needs trend charts (number of detected findings over time) and the calibration curve (precision, recall and FP/FN per threshold from `GET /calibration`, [integration-plan.md](../integration-plan.md) §5, [analytics-plan.md](../analytics-plan.md) §8). The task criteria name two options, Chart.js or Recharts. The stack is React 19 with RTK Query ([0201](0201-web-stack-and-generated-client.md)), and the web rules require presentational components driven by props, with chart components that take their data as props and do not fetch ([`.claude/rules/web-dashboard.md`](../../.claude/rules/web-dashboard.md)).

The choice is hard to reverse once several charts are built, so it is recorded here.

## Options considered

1. **Recharts** (3.11.0, MIT). Charts are React components composed in JSX (`<LineChart data={…}><XAxis …/><Line …/></LineChart>`). Its peer dependency includes `react ^19.0.0`, so it fits the installed React without a wrapper. Data and callbacks arrive as props, the same as any other component.
2. **Chart.js** (4.6.1, MIT) with **react-chartjs-2** (5.3.1, MIT). Chart.js draws imperatively on a canvas from an options object and must register each scale and element. The React binding (`react-chartjs-2`) peers `chart.js ^4.1.1` and wraps a canvas ref. Props feed the options object, and the chart instance lives in the wrapper, so the component is not a plain function of its props.

Both are open source, and both are licensed MIT, which satisfies the web rule.

Evidence from npm metadata (`npm view`, 2026-11-21):

- Recharts 3.11.0 lists peers `react`, `react-dom` and `react-is`, each including `^19.0.0`, plus `@types/react`. `react-is` is a peer, not a dependency, so the install PR must have a `react-is` version matching the installed React 19.
- Package size (`dist.unpackedSize`): Recharts 3.11.0 is about 8.9 MB, Chart.js 4.6.1 is about 6.2 MB and react-chartjs-2 5.3.1 is about 55 kB. This is the size on disk, not the size of the production bundle, which depends on tree-shaking and which charts are used. The bundle size was not measured, because neither library is installed. The install PR measures it with `vite build`.

## Decision

Option 1: **Recharts** is the only chart library in `web/`. Chart components take their data and callbacks as props and do not fetch or read the store.

Rationale: Recharts is declarative, so a chart is a pure function of its props. That matches the props architecture and keeps chart components simple to test with Vitest and Testing Library. Its React 19 peer range covers the installed version. Chart.js would work, but its imperative model adds a wrapper layer and a registration step, and a second chart model would have to be learned for the same job.

## Consequences

- Chart code is declarative JSX, consistent with the rest of `web/`.
- Recharts renders SVG, so very large series (thousands of points) need aggregation on the API side (`GET /stats/trend`, [integration-plan.md](../integration-plan.md) §5, bucketed by hour or day) rather than in the browser. Revisit if the trend view has to show raw series.
- Adding Chart.js later is a new ADR that supersedes this one; no ADR is edited in place.
- Responsive charts (`ResponsiveContainer`) size themselves by measuring the DOM with `ResizeObserver`, which jsdom does not provide. Tests therefore give charts a fixed `width`/`height` or stub `ResizeObserver`. Not verified yet: Recharts is not installed in this repo; confirm when the install PR runs the tests.
- The library is added with `npm install recharts` in `web/`, then `npm audit` is run before merge, as every dependency requires ([CLAUDE.md](../../CLAUDE.md) hard rules).

## Verification note (2026-11-21)

Appended after the install, without changing the decision. The `trend-chart` change installed Recharts 3.11.0 and confirmed the `ResizeObserver` point: tests pass a fixed size or stub it (`web/src/features/trend/components/TrendChart.test.tsx`). Bundle measured with `vite build`: 98 kB to 206 kB gzip with the chart in the main bundle; with `TrendPage` lazy-loaded (`trend-chart-review-fixes`) the main bundle is about 101 kB gzip and the trend chunk about 107 kB gzip. Recharts 3 turns its keyboard `accessibilityLayer` on by default; the trend chart turns it off and offers a data table as the text alternative.
