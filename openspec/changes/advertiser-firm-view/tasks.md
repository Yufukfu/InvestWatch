# Tasks

## 1. Aggregation and data hook

- [x] 1.1 Write failing tests: `aggregate.test.ts` (grouping by advertiser key and firm key, sort by count, repeat flag at 2, finding without firm, without advertiser, non-M1 and duplicate ids ignored) and `useAdvertisers.test.tsx` (requests `module=M1&page_size=200`, page 1 only for total 11, pages 1-3 and not 4 for total 1000, loaded/total counts, error state). Verify they fail first.
- [x] 1.2 Implement `web/src/features/advertisers/model.ts`, `aggregate.ts`, `data/useAdvertisers.ts`. Verify tests, lint, typecheck.
- [x] 1.3 Mutation check, each against `aggregate.test.ts` or `useAdvertisers.test.tsx`: module guard removed; dedupe removed; no-advertiser guard removed; empty-identity guard removed; handle, name and firm-name keys made case-sensitive; profile-URL and website fallbacks dropped; empty firm name treated as a firm (caught as a TypeError inside the pinned case); repeat boundary `>=` to `>`; advertiser and firm sort reversed; tie-break dropped; page count `ceil` to `floor`; page 2 never skipped; page 3 skipped from 2; `module=M1` dropped from the request; later-page error ignored; rows shown on error (refetch failure after success); rows shown before all pages arrived. First run: 5 survived (website fallback, empty firm name, cap, rows on error, partial pages); tests added for 4 of them. The cap mutant (`Math.min(MAX_PAGES, …)` removed) is equivalent: only three hook calls exist, so a 4th page cannot be requested either way (pinned by the page-4 test). mutations: 22 tried, 21 caught, 1 equivalent.

## 2. Table and section

- [x] 2.1 Write failing tests: `AdvertisersTable.test.tsx` (rows, firm counts, `Powtarzający się` only on repeats, `bez dopasowanej firmy`, untrusted name in a `dir="auto"` element, cap text, empty, error, loading) and `AdvertisersPage.test.tsx` (the contract mock renders the four M1 advertisers and no M3 advertiser). Verify they fail first.
- [x] 2.2 Implement `components/AdvertisersTable.tsx`, `AdvertisersPage.tsx`, the section in `App.tsx` and CSS. Verify tests, lint, typecheck (`vite build` not run: shared 8 GB machine, coordinator asked for no builds). `App.test.tsx` API-down case now expects two alerts (findings and advertisers).
- [x] 2.3 Mutation check, each against `AdvertisersTable.test.tsx` or `AdvertisersPage.test.tsx`: repeat label always shown; repeat row class dropped; truncation boundary `>` to `>=`; truncation note dropped; `dir` dropped from name and from handle; handle fallback for a missing name dropped; handle line shown without a name; `bez dopasowanej firmy` dropped; error, loading and empty states dropped; page renders no table. mutations: 13 tried, 13 caught. Review fix (advertiser with only a profile URL or website showed an empty name cell; now shows that contact as plain text): table contact fallback dropped; website fallback dropped; profile/website precedence swapped. mutations: 3 tried, 3 caught.

## 3. Closing

- [x] 3.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 3.2 Run `iw-pr-review` and fix real findings.
