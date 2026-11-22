## 1. Parse the re-scan state in the data hook

- [x] 1.1 Failing tests in `web/src/features/findings/data/rescan.test.ts` and `useFindingDetail.test.tsx`: known states, `current`, missing key (mock), non-object, unknown state, invalid id and time
- [x] 1.2 `web/src/features/findings/data/rescan.ts` `parseRescan(scrapeMeta)` and the `rescan` field on `FindingDetail` (`model.ts`), mapped in `useFindingDetail`
- [x] 1.3 Mutation check: mutations: 10 tried, 10 caught (state conjuncts, current accepted, UUID anchors, id/time type and parse guards, both object guards, mapping dropped; the `typeof id` survivor got the `[uuid]` case)

## 2. Badge and line in the detail panel

- [ ] 2.1 Failing tests in `web/src/features/findings/components/RescanNotice.test.tsx` and one wiring test in `FindingDetailPanel.test.tsx`
- [ ] 2.2 `RescanNotice.tsx` (badge text plus colour, Polish line, UTC time), placed under the source link in `FindingDetailPanel`, styles in `styles.css`
- [ ] 2.3 Mutation check

## 3. Closing

- [ ] 3.1 Apply `iw-docs-update` (`.docs/status/dashboard.md`) and add the `iw-ai-log` entry
- [ ] 3.2 Run `iw-pr-review` and fix real findings
