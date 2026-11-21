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
| 8 | review group 4 | the https origin behind the gateway (X-Forwarded-Proto) was never tested | fix-here (tests with Caddy's forwarded headers: gateway origin accepted, foreign origin refused; engineio 4.15.1 source checked) |
| 9 | review group 4 | an explicit `CORS_ORIGINS` list replaces the same-origin default (confirmed in engineio `_cors_allowed_origins`) | docs (code comment and README: the list must also name the dashboard's own origin) |
| 10 | review group 4 | a failing Socket.IO emit was handled as a Redis outage (resubscribe, health flag down) | fix-here (`Relay._emit` logs and drops the one event; test) |
| 11 | review group 4 | `redis.pubsub()` outside the `try` could end the relay task silently | fix-here (inside the `try`) |
| 12 | review group 4 | cancelling `publish` on the 1 s timeout may leave a pooled connection with an unread reply | wont-fix (redis-py disconnects a connection on cancellation; the hang case is untested, row 5) |
| 13 | review group 4 | no authentication or connection cap on `/events`; event titles and urls reach the browser | wont-fix (v1 decision: no auth behind the localhost gateway; the dashboard renders scraped text as text, `web/CLAUDE.md`) |
| 14 | task 6.2 | end-to-end check, 2026-11-21, Docker 28.5.1, project `iw-api-e2e` (Postgres, Caddy gateway on a spare loopback port, a throwaway Redis; no MinIO): through `https://localhost:<port>` the health was `degraded` with only `minio: down`; a document and finding written with the README SQL as `iw_app` appeared in `GET /api/findings` with `risk_level: high`; two Socket.IO clients connected same-origin; a `finding.created` published on `iw:events` reached client A; `PATCH` to `in_review` reached client B as `finding.updated`; a foreign origin was refused. API logs held no password or URL | docs (copy into the PR body) |
| 15 | task 6.2 | with MinIO down, the SDK's default five retries kept a worker thread busy per health ping | fix-here (urllib3 pool with 2 s connect timeout and no retries; test against an unreachable endpoint) |
| 16 | task 6.1 | the root `compose.yaml` does not include `api/compose.yaml`; `REDIS_URL` and `MINIO_*` come from the `infra-compose` change | new-item (include line and env names with `infra-compose`; api-db-schema follow-up 14) |
