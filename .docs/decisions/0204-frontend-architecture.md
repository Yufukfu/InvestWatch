# 0204. Frontend layering: feature data hooks wrap the generated client, components take props

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from the team's discussion (hooks over container components); accepted by Kacper via PR #11

## Context

The dashboard (`web/`, owner Kacper) is built against a client generated from the contract ([0201](0201-web-stack-and-generated-client.md)). Checked against `web/src` at `main` (`6145997`):

- The three feature components call the generated hooks directly: `FindingsTable.tsx` (40 lines) uses `useGetFindingsQuery`, `SummaryCards.tsx` (21 lines) `useGetStatsSummaryQuery`, `HealthBadge.tsx` (20 lines) `useGetHealthQuery`. `FindingsTable` also reads fields of the generated `Finding` DTO directly.
- `src/api/generated.ts` is produced by `@rtk-query/codegen-openapi` and is RTK-specific (`injectedRtkApi`, `addTagTypes`). Replacing RTK Query means regenerating it with another generator, and every file that imports it changes.
- `src/store.ts` and `src/App.test.tsx` also import `investWatchApi` from `./api/generated`. `App.test.tsx` builds a real store (`configureStore` with the API reducer) and wraps `<App/>` in a Provider, so today no component can be tested with props alone.
- Features still to come (filters, status change, real-time alerts, calibration panel) will each add more such imports.

The web rules already ask for props-driven presentational components ([`.claude/rules/web-dashboard.md`](../../.claude/rules/web-dashboard.md)). This ADR decides where the boundary to the data layer sits.

## Options considered

1. **Feature data hooks as the boundary.** Each feature has a hook in `features/<name>/data/` that calls the generated hooks and returns plain values and callbacks (`{ rows, isLoading, error, onStatusChange }`). A page component calls the hook and renders presentational components with props. Only `src/api/`, `src/store.ts`, the test setup and `features/*/data/` import `generated.ts`.
2. **Container components.** A container component calls the generated hooks and renders a presentational component with props. It gives the same isolation as option 1. The difference is where the data logic lives: in a component, which can only be rendered to be tested and reused, instead of in a hook, which can be tested with `renderHook` and MSW and reused by more than one page.
3. **Status quo.** Components call the generated hooks directly and use the DTO types. Least code now; a library change touches every component and every new feature repeats the coupling.

## Decision

Option 1. The layers, from the bottom:

- `src/api/`: the generated client and `baseApi.ts`. `src/store.ts` and the test setup also import it, since they build the store.
- `src/features/<name>/data/use<Name>.ts`: the feature's hook. The only feature code that imports `generated.ts`. Real-time subscriptions live in the same layer, in an `alerts` feature, because they patch the RTK Query cache and need the generated API.
- `src/features/<name>/model.ts`: app-owned view-model types, **only where the DTO is non-trivial**. `Finding` (with `rules`, `firm`, `advertiser`) gets one. Health and the summary counts are flat, so their hooks return what the component needs and no model or mapper is added.
- `src/features/<name>/components/`: presentational components. They take props and import nothing from `api/`, `data/` or the store, and do not use the DTO types.
- `src/features/<name>/<Name>Page.tsx`: calls a data hook and passes the result to presentational components. This plays the role a container would, and it is the only place where the two meet.

Why hook over container: it is the same separation, but the data logic is a function that composes (several hooks in one page, one hook in several pages) and is tested without rendering. The swap test decides against option 3: with option 1, replacing RTK Query means regenerating `src/api/`, rewriting the `data/` hooks and leaving components and their props tests unchanged; with option 3 it means rewriting every component.

Enforcement: not in place today. The change that implements this ADR adds an oxlint `no-restricted-imports` override for `src/features/*/components/**` (no `api/`, no `data/`, no store), so the main claim becomes a CI check. Until it lands, the rule is reviewer discipline, as the web rules say.

Existing tests: `App.test.tsx` stays as an integration test with a real store (an allowed importer). Presentational components get props-only tests.

## Consequences

- Findings get a view-model type and a mapping step. That is more code than option 3 and is intentional for the one DTO that is non-trivial; the small features do not get one.
- Presentational components are tested with props only, without MSW or a store. Data hooks are tested with MSW handlers from `contracts/mocks/`.
- The existing components (`FindingsTable`, `SummaryCards`, `HealthBadge`) move to this layout in a separate OpenSpec change and PR (`git-guard` denies service code without an active change). This ADR changes no code.
- A future library change is limited to `src/api/` and the `data/` hooks.
