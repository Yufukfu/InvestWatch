# Tasks

## 1. Data hooks and PUT invalidation

- [x] 1.1 Failing tests: `useCalibration(module)` maps the mock and requests the module; nearest-point start index; `useThresholds().save` sends the full body with one module replaced and refetches findings, stats and calibration; 422 gives a Polish error.
- [x] 1.2 Implement model, hooks, `enhanceEndpoints` override for `putSettingsThresholds`, MSW handlers for `/calibration` and `/settings/thresholds`. Tests, lint and typecheck pass.
- [x] 1.3 Mutation check; mutations: 8 tried, 8 caught (tie-break survivor closed with a lower-threshold case)

## 2. Panel, chart and page

- [x] 2.1 Failing component tests: module switch, slider moves between points only and shows values next to the current ones, save disabled when unchanged or saving, warning text, error and empty states, chart accessible name and data table.
- [x] 2.2 Implement `CalibrationPanel`, `CalibrationChart`, `CalibrationPage`; lazy-load the section in `App.tsx`; style. Tests pass.
- [x] 2.3 Mutation check; mutations: 16 tried, 16 caught (three survivors closed: labeled_samples 0 case, no early confirmation, external threshold change)

## 3. Closing

- [x] 3.1 Run against the contract mock server in headless Chrome: move M2 0.5 to 0.7, save, the risk levels in the list change; console clean in the production build; 375 px without page overflow.
- [ ] 3.2 Apply the `iw-docs-update` skill (`.docs/status/dashboard.md`, `web/README.md`, `docs-check` clean) and add the `iw-ai-log` row.
- [ ] 3.3 Run the `iw-pr-review` skill and fix real findings.
