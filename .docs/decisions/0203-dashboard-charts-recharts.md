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

## Decision

Option 1: **Recharts** is the only chart library in `web/`. Chart components take their data and callbacks as props and do not fetch or read the store.

Rationale: Recharts is declarative, so a chart is a pure function of its props. That matches the props architecture and makes chart components testable with Vitest and Testing Library, without a canvas. Its React 19 peer range covers the installed version. Chart.js would work, but its imperative model adds a wrapper layer and a registration step, and a second chart model would have to be learned for the same job.

## Consequences

- Chart code is declarative JSX, consistent with the rest of `web/`.
- Recharts renders SVG, so very large series (thousands of points) need aggregation on the API side (`GET /stats/trend`, [integration-plan.md](../integration-plan.md) §5, bucketed by hour or day) rather than in the browser. Revisit if the trend view has to show raw series.
- Adding Chart.js later is a new ADR that supersedes this one; no ADR is edited in place.
- The library is added with `npm install recharts` in `web/`, then `npm audit` is run before merge, as every dependency requires ([CLAUDE.md](../../CLAUDE.md) hard rules).
