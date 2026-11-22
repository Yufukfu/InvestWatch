---
when: Sat 15:58
who: Kacper
---

## What was done with AI

Turned the task's chart criteria (Chart.js or Recharts) into ADR 0203 with Claude Code: compared the two libraries on npm metadata (licence, React 19 peer range, wrapper needed or not) and wrote the decision and its consequences; then a path-scoped rule `.claude/rules/web-dashboard.md` for the dashboard (props architecture, risk presentation, Polish texts, calibration) from the task criteria

## Outcome / lesson

Recharts chosen for its declarative, prop-driven components. The rule drops the criteria that belong to the analytics rules (R1-R18 identity, forecasts, KNF references) and keeps the ones that govern how risk is shown. Library not installed yet: the install waits for an OpenSpec change
