# Design

## Context

`web/src/features/findings/` is a single table fed by `useFindings()` with a fixed `page=1,page_size=50`. Layering is fixed by [ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md): the data hook is the only feature code importing the generated client, components are presentational. The mock server (`contracts/mock-server`) implements every filter, sort, paging, detail and PATCH in memory with 9 findings; `q` matches title, excerpt, firm and advertiser (see mock-api spec). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** a triage workflow that is pleasant on the 9 mock findings and correct against the contract for any number; URL as the single source of filter state; no new dependency.

**Non-Goals:** realtime updates (next change), calibration, sources, running the real api, client-side filtering or sorting (the backend owns it).

## Decisions

- **URL state with a small hook, no router.** `useFindingsQuery` state (`useUrlState`) reads and writes `window.location.search` through the History API and listens to `popstate`. Parsing validates each value against the contract enums and drops invalid ones. Alternative: `react-router` (a new dependency for one screen, an ADR and an audit, no gain now). The hook lives in `features/findings/data/`.
- **Detail as a side panel in the same page**, selected through `?finding=`. Not a separate route: keeps the list scroll and filters, and needs no router. Native `<dialog>`-free panel with focus return and `Escape` handling so it works in jsdom tests.
- **Filters are controlled components receiving props**; `FindingsPage` wires them to the data hook, per ADR 0204. A `model.ts` holds `FindingFilters`, `FindingRow`, `FindingDetail` view models; the hook maps the DTO.
- **PATCH is not optimistic**: the rules require showing the saved status after the response. The generated `patchFindingsById` invalidates the findings tags through `enhanceEndpoints` so the list refreshes; the detail query is invalidated too.
- **Search debounce 300 ms** in the page component state, committed to the URL once it settles.
- **Styling:** plain CSS in `styles.css` with CSS variables (colour tokens that pass 4.5:1), no CSS framework.

## Risks / Trade-offs

- Mock `q` semantics differ slightly from the openapi text (title only) → the UI sends `q` and shows what comes back; no client assumption.
- History API state handling is hand-rolled → covered by tests for parse, serialise, back/forward.
- Only 9 mock findings hide paging problems → tests use MSW handlers with a larger generated list; the page size control defaults to 25.
