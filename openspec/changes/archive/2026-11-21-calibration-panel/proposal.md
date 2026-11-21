# Proposal

## Why

The dashboard needs a threshold calibration panel ([`web/CLAUDE.md`](../../../web/CLAUDE.md)). The demo script asks for it explicitly: moving the M2 threshold from 0.5 to 0.7 should visibly change FP/FN and the alerts ([analytics-plan.md](../../../.docs/analytics-plan.md) §8, Integration #3). The contract mock server already serves `GET /calibration`, `GET /settings/thresholds` and `PUT /settings/thresholds`, and a PUT recomputes `risk_level` in memory, so the whole flow works without the real backend.

## What Changes

- **Calibration section:** a module switch (M1/M2/M3, default M2) and a threshold slider that moves only between the points returned by `GET /calibration?module=`. It starts at the point nearest `current_threshold`.
- **Values for the selected point:** TP, FP, FN, TN, precision, recall and F1, exactly as returned. Each is shown next to the value at the current threshold, and the count of labelled samples is shown too.
- **Chart:** precision and recall against the threshold (Recharts, [ADR 0203](../../../.docs/decisions/0203-dashboard-charts-recharts.md)), with markers for the current and the selected threshold. A data table gives the text alternative.
- **Saving:** an explicit `Zapisz próg` sends `PUT /settings/thresholds` with all three thresholds, only the chosen module changed. A warning says this is a global change. After a save, findings, stats, calibration and settings refetch, through an `enhanceEndpoints` override per the web rules.

Out of scope: editing the gold set, running `eval/run.py`, a per-rule breakdown, any contract change.

Module: `web/` (Kacper). Routes used: `GET /calibration`, `GET /settings/thresholds`, `PUT /settings/thresholds` (`contracts/openapi.yaml`). No contract, route or event is changed.

## Capabilities

### New Capabilities
- `web-calibration`: the threshold calibration panel. It previews points of the calibration curve and saves a module threshold.

### Modified Capabilities

## Impact

- Code: new `web/src/features/calibration/`, `web/src/api/enhanced.ts` (PUT invalidation), `web/src/App.tsx` (lazy section), tests, the `/calibration` and `/settings/thresholds` MSW handlers, styles.
- Dependencies: none new (Recharts is already in place).
- Docs: `.docs/status/dashboard.md`, `web/README.md`, AI log.
