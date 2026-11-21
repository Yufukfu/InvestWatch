## Why

Kacper's review of PR #21 (`api-v1`, at 8caa046) requested changes. Four findings block approval: `REDIS_URL` has no provider even with #18, the PR leaves `docker compose up` broken on `main` until #18 lands, the `api` service does not wait for Redis and MinIO, and Damian's `.docs/STATUS.md` row is stale. Two are major: `/calibration` returns an empty panel because nothing writes `calibration_points` (the calibration panel is a jury criterion), and `POST /scans` has no documented consumer. Smaller items: the first trend bucket is under-counted, an empty `status` filter is silently ignored, NUL characters give a 500, source URLs are normalised, a threshold-range branch is untested, and Redis outages cost a 2 s timeout on every request.

## What Changes

- **Order:** this branch merges `chore/infra-compose-v2` (#18) and PR #21 is stacked on it: #18 merges first, then #21. No other order leaves `docker compose up` working on `main`.
- `api/compose.yaml`: `REDIS_URL` is built from `REDIS_PASSWORD`; MinIO variables use #18's join-template forms (`${MINIO_ACCESS_KEY:-iw-app}`, `${MINIO_SECRET_KEY:?}`); `api` waits for `redis` (healthy) and `minio-init` (completed). A fresh `scripts/init-env.sh` is then enough for `docker compose up`.
- `GET /calibration` computes the curve from analyst labels in `findings` (`confirmed` = positive, `false_positive` = negative, thresholds 0.05 to 0.95 in steps of 0.05) and falls back to the latest stored `calibration_points` run only when the module has no labels. Response shape unchanged.
- `/stats/trend` counts the whole first bucket (filter on the floored bucket start).
- `GET /findings?status=` with an empty or blank list is 422, as in the mock server.
- `note` (PATCH finding) and source `name`/`schedule_cron` reject NUL characters with 422; `note` is at most 10 000 characters (mock server limit). Source URLs are validated as http(s) and stored exactly as sent.
- Thresholds: after a Redis failure the API skips Redis for 5 s and uses the last known values, instead of waiting for the connect timeout on every request.
- Docs: `.docs/integration-plan.md` names the scraper as owner of the `iw:scan-requests` consumer group and the `scan.*` events; Damian's `.docs/STATUS.md` row; the `.docs/INDEX.md` route for REST and Socket.IO; docstring and comment fixes; follow-ups for the CI gap, the trend default window in the OpenAPI text and the scan consumer.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `rest-api`: calibration from analyst labels; whole first trend bucket; empty `status` filter rejected; NUL and length limits on `note` and source fields; source URL kept as sent; Redis skipped briefly after a failure.

## Impact

- Owner: Damian (`api/`). No contract, REST route or event shape changes; `contracts/` untouched (frozen).
- Merge order: PR #18 (`chore/infra-compose-v2`, Kacper) first, then PR #21. The coordinating session retargets #21's base to `chore/infra-compose-v2`.
- Out of scope: the scan-request consumer itself (scraper, Adam; `openspec/changes/scraper-v1/` is not edited here), CI database services, `finding_status_history`, renaming the doubled CHECK names. All are in `follow-ups.md`.
