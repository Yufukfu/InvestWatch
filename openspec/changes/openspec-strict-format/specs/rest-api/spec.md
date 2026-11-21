## MODIFIED Requirements

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
