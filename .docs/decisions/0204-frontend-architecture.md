# 0204. Frontend layering: feature data hooks wrap the generated client, components take props

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from the team's discussion (hooks over container components); accepted by: pending approval of the PR

## Context

The dashboard (`web/`, owner B) is built against a client generated from the contract ([0201](0201-web-stack-and-generated-client.md)). Today the feature components import the generated hooks directly: `FindingsTable.tsx` calls `useGetFindingsQuery`, `SummaryCards.tsx` calls `useGetStatsSummaryQuery`, `HealthBadge.tsx` calls `useGetHealthQuery`. They also use the generated DTO types (`Finding`, `Status`, `Module`) as their view model.

Two things follow from the code, not from preference:
- `src/api/generated.ts` is produced by `@rtk-query/codegen-openapi` and is RTK-specific (`injectedRtkApi`, `addTagTypes`). Replacing RTK Query means regenerating that file with another generator, and every component that imports it has to change.
- The feature components are small (21 to 40 lines) and have no tests that mock the store. Features still to come (filters, status change, real-time alerts, calibration panel) will each add more such imports.

The web rules already ask for props-driven presentational components ([`.claude/rules/web-dashboard.md`](../../.claude/rules/web-dashboard.md)). This ADR decides where the boundary to the data layer sits.

## Options considered

1. **Feature data hooks as the boundary.** Each feature has a hook in `features/<name>/data/` that calls the generated hooks, maps the DTOs to the feature's own view-model types, and returns plain values and callbacks (`{ rows, isLoading, error, onStatusChange }`). A page component calls the hook and renders presentational components with props. Only `features/*/data/` and `src/api/` import `generated.ts`.
2. **Container components.** A container component calls the generated hooks and renders a presentational component with props. The separation is the same as in option 1, but it adds a component level to the tree and needs a container per view, with no further isolation in React 19 (hooks already compose).
3. **Status quo.** Components call the generated hooks directly and use the DTO types. Lowest code now; a library change touches every component and every new feature repeats the coupling.

## Decision

Option 1. The layers, from the bottom:

- `src/api/`: the generated client only. It is the only place that knows the library. Nothing outside `features/*/data/` imports it.
- `src/features/<name>/model.ts`: view-model types owned by the app (for example `FindingRow`), not the generated DTOs.
- `src/features/<name>/data/use<Name>.ts`: the hook. It is the only place that maps DTOs to view models and calls the generated hooks.
- `src/features/<name>/components/`: presentational components. They take props and import nothing from `api/`, `data/` or the store.
- `src/features/<name>/<Name>Page.tsx`: composes a data hook with presentational components. This is the only layer where the two meet.

The reasoning is the swap test. With option 1, replacing RTK Query means regenerating `src/api/`, rewriting the `data/` hooks and leaving the components and their tests unchanged. With option 3 it means rewriting every component. Option 2 gives the same isolation with an extra component level, and does not fix the library coupling any better than option 1.

SOLID, applied to this layout: one responsibility per layer (SRP); components depend on props, not on a concrete data source (DIP); new features are new folders, not edits to existing components (OCP). No abstraction is added on top of the generated client beyond the hook.

## Consequences

- Each feature has a view-model type and a mapping step. This is more code than option 3 and is intentional: it is what keeps the DTOs from leaking into the UI.
- Presentational components are tested with props only, without MSW or a store. Data hooks are tested with MSW handlers from `contracts/mocks/`.
- Existing components (`FindingsTable`, `SummaryCards`, `HealthBadge`) must be moved to this layout. That is a code change under `web/src`, so it needs an OpenSpec change and its own PR (`git-guard` denies service code without an active change). This ADR does not change code.
- A future library change is limited to `src/api/` and the `data/` hooks; the review rule is that a PR which imports `api/generated` from a component is not ready.
