# Tasks

## 1. URL filter state and findings data hook

- [x] 1.1 Failing tests: `parseFindingParams` drops invalid values and defaults; serialise round-trips; a change of filter resets `page` to 1; hook sends the matching generated-query params. Run `npm test` and see them fail first.
- [x] 1.2 Implement `model.ts` types, URL-state hook and `useFindings` with params and `total`. `npm test`, `npm run lint`, `npm run typecheck` pass.
- [x] 1.3 Mutation check (iw-commit-cycle step 3); mutations: 11 tried, 11 caught

## 2. Filter bar, sort and paging UI

- [x] 2.1 Failing component tests (props only): labelled controls, multi-select status, debounce of `q`, clear-filters, empty and error states, count from `total`.
- [x] 2.2 Implement `FindingsFilters`, paging and sort controls; wire in `FindingsPage`. Tests pass.
- [x] 2.3 Mutation check; mutations: 10 tried, 10 caught

## 3. Table presentation

- [x] 3.1 Failing tests: risk text for each level, score display, detection time, markup rendered as text, scroll container present.
- [ ] 3.2 Implement table upgrade and CSS tokens (AA contrast). Check 375/768/1280 px by hand against the running mock; note result in the commit body.
- [x] 3.3 Mutation check; mutations: 9 tried, 9 caught (one survivor at the 4/5 plural boundary, case added)

## 4. Finding detail panel

- [ ] 4.1 Failing tests with `contracts/mocks/finding-detail.json`: `fail`/`uncertain` rules visible with legal basis and explanation, `pass` group collapsed with count, rule id shown verbatim, 404 state, deep link, `Escape` closes and focus returns.
- [ ] 4.2 Implement detail data hook, panel components and screenshot preview with failure message. Tests pass.
- [ ] 4.3 Mutation check; `mutations: N tried, N caught`.

## 5. Status change

- [ ] 5.1 Failing tests: PATCH body, status shown from response, pending disables, 422/500 shows error and keeps old status, list refreshes; tag invalidation via `enhanceEndpoints`.
- [ ] 5.2 Implement status select, note and save. Tests pass.
- [ ] 5.3 Mutation check; `mutations: N tried, N caught`.

## 6. Closing

- [ ] 6.1 Run against the contract mock server (`docker build -f contracts/mock-server/Dockerfile -t iw-mock-server contracts`, run on :8000, `npm run dev`): filters, detail, status change work and the browser console is clean.
- [ ] 6.2 Apply the `iw-docs-update` skill (docs, `.docs/status/dashboard.md`, `docs-check` clean) and add the `iw-ai-log` row.
- [ ] 6.3 Run the `iw-pr-review` skill and fix real findings.
