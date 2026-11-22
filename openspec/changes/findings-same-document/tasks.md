# Tasks

## 1. Host in the row and document id in the model (no dependency)

- [x] 1.1 Failing tests first: `useFindings.test.tsx` maps `documentId`, `url` and `host`; `FindingsTable.test.tsx` shows `example.com` under the title as text, shows no host for a non-http URL, and shows two rows for M1 and M3 of one document (the M1+M3 pair is built inside the tests: `web/src/test/fixtures/` is synced from `contracts/mocks` and never edited by hand). Verify: `npm test -- findings` shows the new cases failing.
- [x] 1.2 Add `documentId`, `url` and `host` to `FindingRow` and `documentId` to `FindingDetail`, map them in `toRow` and `toDetail` (host via a local `httpHost` in `useFindings.ts` with the same http(s) rule as `safeHttpUrl`: the data layer never imports from `components/`), and render the host in `FindingsTable`. Verify: the tests pass, and `npm run lint` and `npm run typecheck` are clean.
- [x] 1.3 Mutation check (a few hand mutants on the host and the mapping). Record: `mutations: 11 tried, 11 caught` (protocol guard: always true, https only, http only; `hostname`→`host`; catch returns the raw url; `documentId` from `id` in row and detail; `url` dropped; host span removed, shown as url fallback, rendered as a link).

## 2. Module switcher in the detail (starts after the `document_id` contract change is merged)

- [ ] 2.1 Merge `main` with Damian's contract change and regenerate the snapshot and client (`web/README.md` steps). Verify: the generated `GetFindingsApiArg` has `documentId`, and `npm run typecheck` is clean.
- [ ] 2.2 Failing tests first: `useDocumentFindings` sends `document_id` and no list filters, filters the response by `document_id`, and returns empty on error; `FindingsPage.test.tsx` covers switch M1 to M3 (URL, rules, focus), single module (no switcher), sibling error (detail still usable), back button, and the list filtered to M1 (switcher still offers M3). Verify: new cases fail.
- [ ] 2.3 Implement the `useDocumentFindings` hook, the presentational `ModuleSwitcher` (Polish labels, risk as text), and the wiring in `DetailContainer`. Verify: the tests pass, lint and typecheck are clean, and a manual check against the mock server at 375 px and 1280 px with a local M1+M3 fixture.
- [ ] 2.4 Mutation check on the filter by `document_id`, the "more than one" condition and the error path. Record: `mutations: N tried, N caught`.

## 3. Closing

- [ ] 3.1 Apply `iw-docs-update` (`.docs/status/dashboard.md`) and add the `iw-ai-log` row. Verify: `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` exits 0.
- [ ] 3.2 Run `iw-pr-review` and fix real findings. Verify: no blocking finding.

## Workflow follow-up

- `/openspec-archive-change` as the last commit, push `web/findings-same-document`, and open the PR with `Closes #33`. If group 2 is still blocked at hand-in, ship group 1 with `Refs #33`, and keep group 2 as a follow-up change.
