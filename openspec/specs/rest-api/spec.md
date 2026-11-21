# rest-api Specification

## Purpose
Serve the REST API of `contracts/openapi.yaml` v1 under `/api` from the shared database, Redis and MinIO, so the dashboard behaves the same against the real API as against the mocks. Owned by `api/`.

## Requirements

### Requirement: Contract-conformant responses
Every route SHALL be served under the `/api` prefix, and every 2xx, 404 and 422 response body SHALL validate against the matching response schema in `contracts/openapi.yaml` (the finding and document parts of `GET /findings/{id}` are validated separately, see design open question 1). Error bodies SHALL have the shape `{"error": string, "details"?: any}`.

#### Scenario: Every path answers in the contract shape
- **WHEN** the test suite calls each of the 11 paths of `contracts/openapi.yaml` with a valid request on a database seeded from `contracts/mocks/`
- **THEN** each response has the documented status code and its body validates against the documented schema

#### Scenario: Unknown finding
- **WHEN** a client calls `GET /api/findings/{id}` or `PATCH /api/findings/{id}` with a well-formed UUID that has no row
- **THEN** the response is 404 with body `{"error": "..."}`

#### Scenario: Malformed path id
- **WHEN** a client calls `GET /api/findings/not-a-uuid`
- **THEN** the response is 422 with body `{"error": "validation_error", "details": [...]}`

### Requirement: Risk level derived from the current threshold
The API SHALL compute `risk_level` for every finding it returns, and for the `risk_level` filters, from the finding's `score` and the current threshold `t` of its module in Redis `iw:settings:thresholds`: `high` if `score >= t`, `medium` if `score >= t - 0.2`, otherwise `low`. It SHALL NOT store `risk_level`. After a failed Redis read it SHALL use the last thresholds it read successfully, without contacting Redis, for 5 seconds.

#### Scenario: Boundaries with threshold 0.5
- **WHEN** the M2 threshold is 0.5 and M2 findings have scores 0.5, 0.49, 0.3 and 0.29
- **THEN** their `risk_level` values are `high`, `medium`, `medium` and `low`

#### Scenario: Threshold change applies at once
- **WHEN** an M2 finding with score 0.6 is `high` and the M2 threshold is then set to 0.7 through `PUT /api/settings/thresholds`
- **THEN** the next `GET /api/findings/{id}` returns `risk_level: "medium"` without any write to `findings`

#### Scenario: Filter uses the same rule
- **WHEN** a client calls `GET /api/findings?risk_level=high`
- **THEN** every returned item has `risk_level: "high"`, `total` counts exactly the findings whose derived level is `high`, and the same rule is used by `by_risk_level` in `/stats/summary` and by the `risk_level` filter of `/stats/trend`

#### Scenario: Redis unavailable
- **WHEN** Redis is unreachable during a findings request
- **THEN** the API answers with `risk_level` computed from the last thresholds it read successfully (or the defaults 0.6 / 0.5 / 0.7 if it never read any), logs a warning, and `/api/health` reports `redis` as `down`

#### Scenario: No Redis round trip right after a failure
- **WHEN** a thresholds read fails and another request needs thresholds within 5 seconds
- **THEN** the second request uses the last known thresholds without calling Redis, and the first request after the 5 seconds calls Redis again

#### Scenario: Out-of-range value in the key
- **WHEN** the Redis key holds `{"M1": 2, "M2": 0.5, "M3": 0.7}`
- **THEN** the API ignores it, uses the last known thresholds (or the defaults) and logs a warning

### Requirement: Findings list filters, sort and pagination
`GET /api/findings` SHALL apply every filter of the contract together (AND), with `status` as a comma-separated list, `source_id` matched through the finding's document, `score_min` inclusive, `date_from`/`date_to` inclusive on `detected_at`, and `q` as a case-insensitive substring match on `title`, `content_excerpt`, firm name, advertiser name and advertiser handle. It SHALL sort by `sort` (default `-detected_at`) and return `items`, `total`, `page`, `page_size`.

#### Scenario: Combined filters
- **WHEN** a client calls `GET /api/findings?module=M2&status=new,in_review&platform=web`
- **THEN** every item has `module = M2`, `platform = web` and a status of `new` or `in_review`, and `total` is the number of such findings

#### Scenario: Unknown status value
- **WHEN** a client calls `GET /api/findings?status=new,archived`
- **THEN** the response is 422 naming `status`

#### Scenario: Empty status list
- **WHEN** a client calls `GET /api/findings?status=` or `GET /api/findings?status=,`
- **THEN** the response is 422 naming `status`
- **AND** a `status` parameter that is present but names no status SHALL be rejected

#### Scenario: Text search is literal
- **WHEN** a client searches `q=50%` and one finding title contains `50%` while another contains `500`
- **THEN** only the finding containing `50%` is returned (`%` and `_` are not wildcards)

#### Scenario: Page past the end
- **WHEN** there are 60 matching findings and the client asks for `page=3&page_size=50`
- **THEN** `items` is empty, `total` is 60, `page` is 3 and `page_size` is 50

#### Scenario: Page size limit
- **WHEN** a client asks for `page_size=201` or `page=0`
- **THEN** the response is 422

### Requirement: Finding detail with its document
`GET /api/findings/{id}` SHALL return the finding with `risk_level`, its `document` in the `ScrapedDocument` shape, and `screenshot_urls` holding `/api/documents/{document_id}/screenshot/{viewport}` for each viewport that has a screenshot key.

#### Scenario: Document with two screenshots
- **WHEN** the finding's document has `screenshots` for `desktop` and `mobile` only
- **THEN** `screenshot_urls` has exactly the keys `desktop` and `mobile`, each pointing to the screenshot route

#### Scenario: Document without screenshots
- **WHEN** the finding's document has no `screenshots`
- **THEN** `screenshot_urls` is an empty object and `document` is still present

### Requirement: Status and note changes
`PATCH /api/findings/{id}` SHALL accept a body with `status` and/or `note` only, store the change, set `updated_at` to the current UTC time, return the updated finding, and publish a `finding.updated` event `{id, status}` on Redis `iw:events` after the database commit. `note` SHALL be at most 10 000 characters and SHALL NOT contain NUL characters.

#### Scenario: Status change
- **WHEN** an analyst sends `{"status": "confirmed"}` for a `new` finding
- **THEN** the response is 200 with `status: "confirmed"` and a later `updated_at`, the row is updated, and one `finding.updated` event with that id and status is published

#### Scenario: Note only
- **WHEN** an analyst sends `{"note": "sprawdzone"}`
- **THEN** the note is stored, the status is unchanged and a `finding.updated` event with the unchanged status is published

#### Scenario: Clearing a note
- **WHEN** an analyst sends `{"note": null}`
- **THEN** the stored note becomes null

#### Scenario: Invalid bodies
- **WHEN** the body is `{}`, `{"status": null}`, `{"status": "archived"}`, `{"score": 1}`, a `note` containing a NUL character or a `note` longer than 10 000 characters
- **THEN** the response is 422, nothing is stored and no event is published

#### Scenario: Redis down after commit
- **WHEN** the database update commits but publishing to `iw:events` fails
- **THEN** the response is still 200 with the updated finding and the failure is logged as an error

### Requirement: Statistics
`GET /api/stats/summary` SHALL count all findings by module, status, platform and derived risk level, with every module, status and risk level present (zero if none), and `last_scan_at` as the latest `sources.last_run_at`. `GET /api/stats/trend` SHALL count findings per module in UTC `hour` or `day` buckets of `detected_at`, with filters `module`, `risk_level`, `date_from`, `date_to`, and SHALL return a point for every bucket in the range, including empty ones.

#### Scenario: Empty database
- **WHEN** there are no findings and no sources have run
- **THEN** `/stats/summary` returns `total: 0`, zero counts for `M1, M2, M3`, every status and every risk level, and `last_scan_at: null`

#### Scenario: Day buckets
- **WHEN** a client calls `/stats/trend?bucket=day&date_from=2026-11-20T00:00:00Z&date_to=2026-11-21T23:59:59Z` and findings exist only on Nov 21
- **THEN** `points` has two items, `2026-11-20T00:00:00Z` with all zeros and `2026-11-21T00:00:00Z` with the counts

#### Scenario: Module filter keeps the shape
- **WHEN** a client calls `/stats/trend?module=M1`
- **THEN** every point still has `M1`, `M2` and `M3`, with `M2` and `M3` equal to 0

#### Scenario: Whole first bucket
- **WHEN** a finding was detected at 10:10 and a client calls `/stats/trend?bucket=hour&date_from=<day>T10:30:00Z&date_to=<day>T11:30:00Z`
- **THEN** the `10:00` point counts that finding
- **AND** the first bucket SHALL count its whole period, from the bucket start, even when `date_from` falls inside it

### Requirement: Calibration curve
`GET /api/calibration?module=` SHALL compute the precision/recall curve from analyst labels on that module's findings: `confirmed` is a positive, `false_positive` a negative, other statuses are unlabeled. For each threshold `t` in 0.05, 0.10, ..., 0.95 it SHALL count `tp` (positive, `score >= t`), `fp` (negative, `score >= t`), `fn` (positive, `score < t`) and `tn` (negative, `score < t`), with `precision`, `recall` and `f1`. `current_threshold` SHALL come from `iw:settings:thresholds`.

#### Scenario: Curve from analyst labels
- **WHEN** M2 has confirmed findings with scores 0.9 and 0.4 and false positives with scores 0.6 and 0.2
- **THEN** `labeled_samples` is 4, there are 19 points from 0.05 to 0.95, and the point at 0.5 has `tp: 1, fp: 1, fn: 1, tn: 1, precision: 0.5, recall: 0.5, f1: 0.5`

#### Scenario: Metric formulas
- **WHEN** a point is computed for threshold `t`
- **THEN** it SHALL have `precision = tp / (tp + fp)` (1.0 when nothing is predicted positive), `recall = tp / (tp + fn)` (0.0 without positives) and `f1` their harmonic mean (0.0 when both are 0), each rounded to 3 decimals

#### Scenario: Unlabeled findings do not count
- **WHEN** M2 also has findings with status `new`, `in_review` or `closed`
- **THEN** they change neither `labeled_samples` nor any count
- **AND** `labeled_samples` SHALL be the number of labeled findings

#### Scenario: Nothing predicted positive
- **WHEN** no labeled finding has a score at or above a threshold
- **THEN** that point has `precision: 1.0` and `recall: 0.0`

#### Scenario: Labels win over a stored run
- **WHEN** M2 has labeled findings and also a stored calibration run
- **THEN** the curve is computed from the labels

#### Scenario: Stored run when there are no labels
- **WHEN** M2 has no labeled findings and two stored runs exist
- **THEN** only the newer run's points are returned, sorted by threshold, with that run's `labeled_samples`
- **AND** when the module has no labeled findings, the endpoint SHALL return the points and `labeled_samples` of the latest `calibration_points` run for that module instead (ascending threshold)

#### Scenario: No labels and no run
- **WHEN** M3 has no labeled findings and no stored run
- **THEN** the response is 200 with `points: []`, `labeled_samples: 0` and the current M3 threshold

#### Scenario: Module missing
- **WHEN** a client calls `/api/calibration` without `module`
- **THEN** the response is 422

### Requirement: Thresholds setting
`GET /api/settings/thresholds` SHALL return the thresholds from Redis key `iw:settings:thresholds`, first writing the defaults `{"M1": 0.6, "M2": 0.5, "M3": 0.7}` if the key is missing. `PUT` SHALL validate the body (all three modules, numbers in [0, 1], no other keys), replace the key and return the saved value.

#### Scenario: Missing key
- **WHEN** the key does not exist and a client calls `GET /api/settings/thresholds`
- **THEN** the response is the defaults and the key now holds them

#### Scenario: Valid update
- **WHEN** a client sends `PUT {"M1": 0.6, "M2": 0.7, "M3": 0.7}`
- **THEN** the response echoes it and a direct read of the Redis key returns the same values

#### Scenario: Invalid update
- **WHEN** a client sends a body missing `M3`, with `M2: 1.5`, or with an extra key `M4`
- **THEN** the response is 422 and the stored thresholds are unchanged

#### Scenario: Redis down on update
- **WHEN** Redis is unreachable during `PUT`
- **THEN** the response is 503 with an error body and nothing is changed

### Requirement: Sources management
`GET /api/sources` SHALL list all sources with `documents_count` computed from `documents`. `POST /api/sources` SHALL require `name`, `platform`, `url`, `source_kind` and `target_modules`, generate a UUID v4 id, default `active` to true and `schedule_cron` to null, and return 201 with the full `Source`. `PATCH /api/sources/{id}` SHALL apply a partial update where only `schedule_cron` may be set to null. `name` and `schedule_cron` SHALL NOT contain NUL characters.

#### Scenario: Create a source
- **WHEN** a client posts a valid source without `active`
- **THEN** the response is 201 with a new id, `active: true`, `documents_count: 0`, and the row exists

#### Scenario: Create with missing field
- **WHEN** a client posts a source without `url`
- **THEN** the response is 422 and no row is created

#### Scenario: URL kept as sent
- **WHEN** a client posts `url: "https://Alfa.example"` (no trailing slash, mixed case)
- **THEN** the stored and returned `url` is exactly `https://Alfa.example`
- **AND** `url` SHALL be stored exactly as sent

#### Scenario: URL a parser could read differently
- **WHEN** a client posts a `url` with a leading space, a trailing newline, a tab, a NUL, a DEL or a backslash (for example `https://good.example\@evil.example`)
- **THEN** the response is 422 and no row is created
- **AND** `url` SHALL be an http(s) URL without credentials, whitespace, control characters or backslashes

#### Scenario: NUL in a text field
- **WHEN** a client posts or patches a `name` or `schedule_cron` containing a NUL character
- **THEN** the response is 422 and nothing changes

#### Scenario: Deactivate a source
- **WHEN** a client sends `PATCH {"active": false}`
- **THEN** only `active` changes and the response is the full updated source

#### Scenario: Invalid patch
- **WHEN** a client sends `PATCH {}`, `{"name": null}` or `{"target_modules": []}`
- **THEN** the response is 422 and nothing changes

#### Scenario: Unknown source
- **WHEN** a client patches a source id that does not exist
- **THEN** the response is 404

### Requirement: Manual scan request
`POST /api/scans` SHALL check that the source exists, add `source_id` and `requested_at` (UTC) to Redis Stream `iw:scan-requests` in the shape of `contracts/schemas/events.schema.json` (`scan_request`), and return 202 `{"queued": true, "source_id": ...}`.

#### Scenario: Scan queued
- **WHEN** a client posts an existing `source_id`
- **THEN** the response is 202 and one new entry with that `source_id` and a valid `requested_at` is on `iw:scan-requests`

#### Scenario: Unknown source
- **WHEN** a client posts a `source_id` with no row
- **THEN** the response is 404 and nothing is added to the stream

#### Scenario: Redis down
- **WHEN** Redis is unreachable
- **THEN** the response is 503 with an error body

### Requirement: Screenshot proxy
`GET /api/documents/{id}/screenshot/{viewport}` SHALL stream the object named by the document's `screenshots[viewport]` key from MinIO bucket `iw-raw` with content type `image/png`. It SHALL only read keys stored on the document row, never a key taken from the request.

#### Scenario: Screenshot exists
- **WHEN** the document has a `desktop` screenshot key and the object exists
- **THEN** the response is 200, `image/png`, with the object's bytes

#### Scenario: No such screenshot
- **WHEN** the document does not exist, has no key for the viewport, or the object is missing in MinIO
- **THEN** the response is 404 with an error body

#### Scenario: Viewport not in the enum
- **WHEN** a client asks for viewport `watch`
- **THEN** the response is 422

#### Scenario: MinIO down
- **WHEN** MinIO is unreachable
- **THEN** the response is 503 with an error body

### Requirement: Health
`GET /api/health` SHALL check Postgres (`SELECT 1`), Redis (`PING`) and MinIO (bucket `iw-raw` exists), each with a timeout of at most 2 seconds, and return `services` with `api`, `postgres`, `redis`, `minio`. `status` SHALL be `down` if Postgres is down, `degraded` if Redis or MinIO is down, otherwise `ok`.

#### Scenario: All up
- **WHEN** all three dependencies answer
- **THEN** the response is 200 with `status: "ok"` and every service `ok`

#### Scenario: MinIO down
- **WHEN** MinIO does not answer within the timeout
- **THEN** the response is 200 within 3 seconds with `status: "degraded"` and `minio: "down"`

#### Scenario: Postgres down
- **WHEN** Postgres is unreachable
- **THEN** the response is 200 with `status: "down"` and `postgres: "down"`
