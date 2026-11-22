# Follow-ups

| Item | Disposition |
|---|---|
| A "changed"/"removed" badge on the findings list needs the state on `Finding`, which is closed. Proposed: optional `rescan_state` (`current`/`changed`/`removed`) in `finding.schema.json`, a v1 contract change for the whole team. | Deferred: contracts frozen; detail panel only until the team agrees. |
| `removed` from a job error needs the scraper to write `job_errors.url` (today it writes only `source_id`, `reason`, `detail`) or a document row with `http_status` 404/410 (Adam's part of #71). | Adam (scraper), issue #71. |
| The mock server and `contracts/mocks/finding-detail.json` do not carry `scrape_meta.rescan`; the dashboard's mock mode shows no badge. | Kept as is (mocks stay a test double, api/CLAUDE.md); Kacper treats a missing key as `current`. |
| Another source's later fetch of the same URL is not counted (the page key includes `source_id`). | Accepted: re-scans of a source keep its `source_id`. |
