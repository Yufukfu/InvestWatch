# Tasks

## 1. Contract snapshot

- [x] 1.1 Regenerate `web/src/api/openapi.json` and `generated.ts` from `contracts/openapi.yaml` 1.2.0 (`npm run api:generate`); `npm run contracts:check` is clean. mutations: n/a, generated files only (no hand-written logic)

## 2. Export link in the detail

- [x] 2.1 Write failing tests: `useFindingDetail` maps `exportUrl` to `<API base>/findings/<id>/export?format=html`; the detail panel shows an `Eksportuj` link with that `href`, `target="_blank"` and `rel="noopener noreferrer"` when the detail is loaded, and none while loading, on 404 or on an error with no data; the untrusted-text test lists the export link among the detail's links. Verify they fail first.
- [x] 2.2 Add `exportUrl` to the view model and the hook, render the link in the detail header. Verify tests, lint, typecheck, build.
- [x] 2.3 Mutation check (iw-commit-cycle step 3), on the mutants chosen by the agent, each run against `FindingDetailPanel.test.tsx`, `useFindingDetail.test.tsx` and `untrustedText.test.tsx`: `!notFound` dropped from the link guard; `exportUrl` dropped from the guard (an `<a>` with no `href` while loading, which a role query would miss, so the negative test queries by text); `target="_blank"` dropped; `rel` dropped; `?format=html` dropped (JSON pack); API base hard-coded to `/api`. `encodeURIComponent` around the id is not mutated: ids are UUIDs, so dropping it is equivalent. mutations: 6 tried, 6 caught

## 3. Closing

- [x] 3.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [x] 3.2 Run `iw-pr-review` and fix real findings. Group and whole-branch review (security: yes): no blocking findings. Could not check: the live api page behind the gateway at runtime.
