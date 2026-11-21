# Tasks

## 1. List: last result while loading, search box, URL history

- [x] 1.1 Failing tests: rows and pager stay mounted with `aria-busy` and focus kept on a sort header and on `Następna strona` during a refetch; the search keeps a trailing space; reset cancels a pending debounce; a settled search replaces the history entry and a module change pushes one; restored tests (raw status fallback, error beats stale rows, platform/module/score cells, full row mapping, page size in the request); page wiring (pager, page size, sort, first page) sends the right params; `platform`, `q` and date inputs reach the request; exact serialised param names; plurals 11/14/21/24.
- [x] 1.2 Implement in `useFindings`, `findingsUrl`, `useUrlSearch`, `FindingsTable`, `FindingsFilters`, `FindingsPage`. Tests, lint and typecheck pass.
- [x] 1.3 Mutation check covering every changed guard plus the survivors Adam listed for this group; mutations: 5 tried, 5 caught (one survivor closed with a success-then-error case); Adam's survivors for this group are now pinned by tests (pager/page size/sort/first-page wiring, platform/q/date params, serialised names, plurals 11/14/21/24, restored table tests)

## 2. Detail and status change

- [x] 2.1 Failing tests: the editor keeps focus after a save (no re-mount) and the live region is always present; a second submit while saving sends no second PATCH; the panel portal makes the rest of the page `inert` and locks scroll, and both are restored on close; Escape in a filled field focuses `Zamknij`, a second Escape closes; a failed refetch keeps the detail with an inline alert; a changed id never shows the previous detail; screenshot paths `//evil.example/x.png` and `/other/x.png` are not loaded.
- [x] 2.2 Implement in `StatusEditor`, `useStatusChange`, `FindingDetailPanel`, `useFindingDetail`, `FindingsPage`. Tests pass.
- [x] 2.3 Mutation check (changed guards plus Adam's survivors for this group); mutations: 9 tried, 9 caught (two equivalent mutants found, the redundant conditions removed)

## 3. Lint, contrast and closing

- [x] 3.1 Enable `react/exhaustive-deps` in `web/.oxlintrc.json`; inputs and chips get `#6b7280` borders. `npm run lint` clean; check the contrast values in a browser run.
- [x] 3.2 Browser run against the mock at 375/768/1280 px: keyboard sort and paging keep focus, save keeps focus in the panel, Escape behaviour, console clean in the production build.
- [x] 3.3 Add a note to the archived `findings-explorer/tasks.md` mutation lines; apply `iw-docs-update` (`.docs/status/dashboard.md`) and add the `iw-ai-log` row.
- [ ] 3.4 Run `iw-pr-review`, fix real findings, then reply on PR #39 to each review point.
