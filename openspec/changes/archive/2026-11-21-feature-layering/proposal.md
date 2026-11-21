# Proposal

## Why

The dashboard's three feature components (`FindingsTable`, `SummaryCards`, `HealthBadge`) call the generated RTK Query hooks directly and read the generated `Finding` DTO. `generated.ts` is RTK-specific, so replacing the data library, or adding any component test without a real store, means touching every component, and each planned feature (filters, status change, alerts, calibration, trend chart) would repeat the coupling. [ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md) decides the layering; this change applies it before more features land on the old shape.

## What Changes

- Move each of the three features to the layout from ADR 0204: `features/<name>/data/use<Name>.ts` (the only feature code that imports `api/generated`), `features/<name>/components/` (presentational, props only), and `features/<name>/<Name>Page.tsx` (calls the hook, passes props).
- `findings` gets an app-owned view model (`model.ts`) because the `Finding` DTO is non-trivial. `health` and `summary` return the plain values their components need; no model or mapper.
- Add an oxlint `no-restricted-imports` override for `src/features/*/components/**` (no `api/`, `data/`, store) so the layering is a CI check instead of reviewer discipline. Verified that oxlint 1.94.0 reports it in an `overrides` block.
- Tests: `App.test.tsx` stays as the integration test with a real store; add props-only component tests and an MSW data-hook test per feature.
- No change to what the user sees: same Polish texts, same loading, error and down states.

**Out of scope:** new features (filters, trend chart, alerts, calibration panel, status change), the `recharts` install and the trend chart (separate change `trend-chart`), contracts, REST routes and events. This change touches no contract, route or event. Kacper's module owns it.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-foundation`: adds a requirement that feature components are presentational and that the data layer is reachable only through feature data hooks, enforced by lint.

## Impact

- Code: `web/src/features/**` (restructured), `web/.oxlintrc.json` (override), `web/src/App.tsx` (renders the pages), tests under `web/src/`.
- Dependencies: none added.
- Docs: `web/CLAUDE.md` and `.claude/rules/web-dashboard.md` already describe the target layout (ADR 0204, PR #11); STATUS row and AI log row updated at the end. This change depends on PR #11 for the ADR; it is stacked on that branch.
