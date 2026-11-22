# Tasks

## 1. Aggregation and data hook

- [ ] 1.1 Write failing tests: `aggregate.test.ts` (grouping by advertiser key and firm key, sort by count, repeat flag at 2, finding without firm, without advertiser, non-M1 and duplicate ids ignored) and `useAdvertisers.test.tsx` (requests `module=M1&page_size=200`, page 1 only for total 11, pages 1-3 and not 4 for total 1000, loaded/total counts, error state). Verify they fail first.
- [ ] 1.2 Implement `web/src/features/advertisers/model.ts`, `aggregate.ts`, `data/useAdvertisers.ts`. Verify tests, lint, typecheck.
- [ ] 1.3 Mutation check.

## 2. Table and section

- [ ] 2.1 Write failing tests: `AdvertisersTable.test.tsx` (rows, firm counts, `Powtarzający się` only on repeats, `bez dopasowanej firmy`, untrusted name in a `dir="auto"` element, cap text, empty, error, loading) and `AdvertisersPage.test.tsx` (the contract mock renders the four M1 advertisers and no M3 advertiser). Verify they fail first.
- [ ] 2.2 Implement `components/AdvertisersTable.tsx`, `AdvertisersPage.tsx`, the section in `App.tsx` and CSS. Verify tests, lint, typecheck, build.
- [ ] 2.3 Mutation check.

## 3. Closing

- [ ] 3.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 3.2 Run `iw-pr-review` and fix real findings.
