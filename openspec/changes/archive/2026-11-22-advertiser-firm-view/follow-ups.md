# Follow-ups

| # | Item | Disposition |
|---|---|---|
| 1 | `web/src/api/openapi.json` is stale against `contracts/openapi.yaml` 1.2.0 (the `GET /findings/{id}/export` route from PR #109), so `contracts.test.ts` fails on `main` and on this branch. Not caused by this change, which reads `GET /findings` only. Fix: `npm run api:generate` in its own PR. | new-item (report to the web owner; not opened from this sub-agent) |
| 2 | Same advertiser under two handles shows as two rows (no fuzzy matching). | wont-fix (design.md, Risks: exact keys only for the demo) |
| 3 | More than 600 M1 findings: the table covers the most recent 600, stated in the UI. An aggregate endpoint would lift the cap and needs the team's OK (issue #72). | wont-fix (design.md, decision 1) |
