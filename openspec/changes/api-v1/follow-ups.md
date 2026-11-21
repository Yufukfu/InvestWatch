# Follow-ups: api-v1

Out-of-scope or "declined to judge" items from reviews, each with one disposition (`fix-here`, `new-item`, `wont-fix`, `docs`).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | design open question 1 (coordinator decision) | `GET /findings/{id}` response schema in `contracts/openapi.yaml` combines `allOf: [finding.schema.json]` (`additionalProperties: false`) with extra `document` and `screenshot_urls`, so no real response validates | new-item (contract v1.1 for the team); tests validate the finding and document parts separately |
| 2 | design open question 2 (coordinator decision) | `SourceInput` has no `required` list; `POST /sources` requires `name, platform, url, source_kind, target_modules`, as the mock server did | docs (README) |
| 3 | review groups 1-3 | `page=10**12` overflowed OFFSET and a NUL in `q`/`platform` reached Postgres: plain-text 500 | fix-here (`page <= 100000`, `q <= 200` and `platform <= 32` characters without NUL, 422; tests) |
| 4 | review groups 1-3 | no handler for unexpected errors: 500 without the contract error shape | fix-here (catch-all returns `{"error": "internal error"}`, logs only the class; test with Postgres down) |
| 5 | review groups 1-3 | `publish_event` could hold a PATCH response for the Redis socket timeout (5 s) | fix-here (publish wrapped in a 1 s timeout; not covered by a test, a hanging Redis is hard to fake) |
| 6 | review groups 1-3 | the detail `document` exposes `html_object_key` and screenshot keys (bucket layout) | wont-fix (fields of the `ScrapedDocument` contract; keys are only usable through the API, which reads keys from the row) |
| 7 | review groups 1-3 | count and page are two queries, not one snapshot | wont-fix (hackathon volume; a moving `total` while findings arrive is acceptable) |
