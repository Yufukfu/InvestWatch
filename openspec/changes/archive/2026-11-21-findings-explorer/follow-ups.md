# Follow-ups: findings-explorer

From the whole-branch `iw-reviewer` pass (findings 1-6 and 8 were fixed in this branch).

| Item | Disposition |
|---|---|
| "Zapisano." shows a moment before the refetched status; a failed refetch turns the panel into the load-error state | wont-fix: the window is one GET; the form already resets to the API's values when the refetch lands. Revisit if the real api is slow |
| `/api/../x` screenshot path would pass the `/api/` prefix check | wont-fix: the URL comes from our own API, the request stays same-origin and is an image GET |
| Screenshots disappear silently if `VITE_API_BASE_URL` is not `/api` | docs: same-origin `/api` is the only supported setup (ADR 0206, `web/README.md`) |
| Every filter change and row selection adds a history entry | wont-fix: intended, the back button restores the previous view (spec "Filter state lives in the URL") |
| `date_to` is sent as `T23:59:59Z`, excluding the last sub-second of the day | wont-fix: detection times are whole seconds in the contract mocks and the api |
| Opening another row while a panel is open returns focus to the first opener | wont-fix: the modal backdrop and focus trap prevent reaching another row |
| Paging is unit-tested through props, not with a large generated MSW list as design.md said | wont-fix: the pager and `withFilter` page reset are covered; the mock has 9 findings |
| Layout at 375 px and AA contrast are checked by hand (headless Chrome run), not by an automated test | new-item: add a Playwright smoke test once the demo stack runs in compose |
