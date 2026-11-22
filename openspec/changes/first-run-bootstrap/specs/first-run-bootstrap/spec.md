# Spec Delta

## Purpose

What a first `docker compose up` on a clean clone leaves behind and how an operator checks it: every never-run source scanned, documents analysed into findings for M1, M2 and M3, and a calibration curve, with no manual scan request.

## ADDED Requirements

### Requirement: Never-run sources are scanned on start
A one-shot `bootstrap` service SHALL, after `seed` completed and `worker` is healthy, enqueue one scan request on `iw:scan-requests` for every active, collectable source that has a `schedule_cron` and a null `last_run_at`, and exit 0.

#### Scenario: Clean clone
- **WHEN** `docker compose up` runs on empty volumes with the default seeds
- **THEN** one request is enqueued per seeded source that has a cron (17 with the shipped seeds), `bootstrap` exits 0, and each gets a `scan.started` and a `scan.finished` event without any `POST /api/scans`

#### Scenario: Inactive source
- **WHEN** a source has `active = false`
- **THEN** no request is enqueued for it

#### Scenario: Manual source
- **WHEN** an active source has no `schedule_cron` (the shipped X and YouTube rows)
- **THEN** no request is enqueued for it

#### Scenario: Redis unreachable
- **WHEN** `bootstrap` cannot reach Redis
- **THEN** it exits non-zero with the reason in its JSON log and enqueues nothing

### Requirement: Bootstrap is idempotent
`bootstrap` SHALL NOT enqueue a request for a source that has run or whose request is still unconsumed, so a restart, a second `up` or a rerun never duplicates a scan.

#### Scenario: Second up on the same volumes
- **WHEN** the stack is started again after every source ran
- **THEN** `bootstrap` exits 0 and enqueues no request

#### Scenario: Rerun while requests are pending
- **WHEN** `bootstrap` runs twice before `worker` consumed the first batch
- **THEN** the stream holds one request per source, not two

#### Scenario: Source that failed
- **WHEN** a source's first scan ended `failed` and set `last_run_at`
- **THEN** `bootstrap` does not enqueue it again (its retry is the scheduler's or an analyst's)

### Requirement: Bootstrap can be disabled
With `BOOTSTRAP_SCAN=false` the `bootstrap` service SHALL exit 0 without reading `sources` or writing to Redis, so a deployment that wants cron-only collection keeps it.

#### Scenario: Disabled
- **WHEN** `BOOTSTRAP_SCAN=false`
- **THEN** `bootstrap` logs that it is disabled, exits 0, and the stream is unchanged

#### Scenario: Not a boolean
- **WHEN** `BOOTSTRAP_SCAN` is neither `true` nor `false`
- **THEN** `bootstrap` exits non-zero naming the variable, and `worker` and `scheduler` are unaffected

### Requirement: Bootstrap holds the least privilege it needs
`bootstrap` SHALL receive the app database role and the Redis URL only, no MinIO credential, no admin value and no host port, with the scraper container hardening.

#### Scenario: Environment and settings
- **WHEN** the compose model is read
- **THEN** `bootstrap` has no `MINIO_*` variable, uses the app role in `DATABASE_URL`, is on `data` only, and is read-only with all capabilities dropped and `restart: "no"`

### Requirement: Readiness is verifiable
`python -m iw_scraper.bootstrap status` SHALL print, as JSON on stdout, per source its state (`scanned`, `failed` with the job error reason, `pending`, or `manual` for a never-run source without a cron) and the counts of documents, findings per module and `calibration_points` per module, and SHALL exit 0 only when every module M1, M2 and M3 has at least one finding and no source is `pending`.

#### Scenario: Complete run
- **WHEN** documents were analysed and every module has a finding and calibration points
- **THEN** `status` exits 0 and lists no `pending` source

#### Scenario: Still running
- **WHEN** some sources are `pending` or a module has no finding yet
- **THEN** `status` exits 1, names the modules with none and the pending sources, and changes no data

#### Scenario: Blocked source and manual source
- **WHEN** a scheduled source failed with `blocked` and the X and YouTube rows never ran
- **THEN** `status` lists the first as `failed` with the reason and the others as `manual`, and exits 0 if every module has a finding

#### Scenario: Database unreachable
- **WHEN** `status` cannot connect to Postgres
- **THEN** it exits 2 with the reason on stderr and prints no partial report

### Requirement: The brief is traced to evidence
`.docs/brief-compliance.md` SHALL list every requirement of the challenge brief (modules 1 to 3, sections 3, 5 and 6) with the file, spec or command that shows it met, or the gap, and `docs-check` SHALL fail if a path it cites does not exist.

#### Scenario: Gap is stated
- **WHEN** the file is read
- **THEN** Facebook, Instagram and TikTok collection is listed as not covered with a link to ADR 0103

#### Scenario: Broken evidence path
- **WHEN** an evidence path in the file does not exist
- **THEN** `docs-check` exits non-zero naming the path
