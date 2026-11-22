# scraper-deployment Specification

## Purpose

How the scraper runs inside the one-command stack: which services start, with which credentials and networks, in which order, on which schedule, and what they refuse to hold.

## Requirements

### Requirement: Scraper services start with the stack
The root `docker compose up` SHALL start a `worker`, a `scheduler` and a one-shot `seed` from the scraper image, with no extra command.

#### Scenario: Whole stack starts
- **WHEN** `docker compose up` runs on a clone with a generated `.env`
- **THEN** `seed` exits 0, `worker` becomes healthy and `scheduler` is running with `RestartCount` 0 after a settle time

#### Scenario: Single scheduler
- **WHEN** the compose model is read with `docker compose config`
- **THEN** `scheduler` is defined once, has no `container_name` and no `deploy.replicas` above 1

#### Scenario: Crash is restarted
- **WHEN** the compose model is read
- **THEN** `worker` and `scheduler` have `restart: unless-stopped` and `seed` has `restart: "no"`

### Requirement: Start order
`worker` and `scheduler` SHALL start only after `api-migrate`, `seed` and `minio-init` completed successfully and Postgres and Redis are healthy. `seed` SHALL start only after `api-migrate` completed and Postgres is healthy.

#### Scenario: Gates are declared
- **WHEN** the model is read with `docker compose config --format json`
- **THEN** `worker` and `scheduler` depend on `api-migrate`, `seed` and `minio-init` with `service_completed_successfully` and on `postgres` and `redis` with `service_healthy`, and `seed` depends on `api-migrate` and `postgres`

#### Scenario: Seed fails
- **WHEN** `seed` is overridden to exit 1 and the stack starts
- **THEN** `worker` and `scheduler` are never started

#### Scenario: Seed rerun
- **WHEN** the stack is started a second time on the same volumes
- **THEN** `seed` exits 0 and `sources` holds exactly one row for the KNF URL

### Requirement: Seeded source is scheduled
`seed` SHALL pass a cron expression, from `SCRAPER_SEED_CRON` with a default, so the seeded source is enqueued by the scheduler without a manual scan.

#### Scenario: Cron is set
- **WHEN** `seed` has run with the default
- **THEN** the KNF row in `sources` has a non-null `schedule_cron` that `croniter` accepts

#### Scenario: Invalid cron
- **WHEN** `SCRAPER_SEED_CRON` is not a valid 5-field cron
- **THEN** `seed` exits non-zero and no row is written

### Requirement: Least-privilege credentials
Scraper services SHALL receive their secrets only from the root `.env`, with no default, and SHALL hold no admin credential. `seed` SHALL receive the database URL only.

#### Scenario: No default for a secret
- **WHEN** `scraper/compose.yaml` is read
- **THEN** `DATABASE_URL`, `REDIS_URL` and `MINIO_SECRET_KEY` use the required-variable form and carry no fallback value

#### Scenario: No admin credential
- **WHEN** the environment of `worker`, `scheduler` and `seed` is inspected
- **THEN** none contains the admin password string or the admin user name, and the `DATABASE_URL` user is the app role

#### Scenario: Seed holds less
- **WHEN** the environment of `seed` is inspected
- **THEN** it has no `REDIS_URL` and no `MINIO_*` variable

### Requirement: Isolated networks and no published port
Scraper services SHALL attach to `data` and `egress` only and SHALL publish no host port.

#### Scenario: Not reachable from outside
- **WHEN** the running stack is inspected
- **THEN** no scraper container publishes a port and none is on `edge`

#### Scenario: Health is internal
- **WHEN** a throwaway container on the `data` network requests `GET /health` of `worker` on `SCRAPER_HEALTH_PORT`
- **THEN** it answers 200, while the same port on the host refuses the connection

### Requirement: Hardened containers
Scraper containers SHALL run as a non-root user with a read-only root filesystem, a `/tmp` tmpfs, all capabilities dropped, `no-new-privileges` and CPU and memory limits.

#### Scenario: Container settings
- **WHEN** `docker inspect` is run on `worker`, `scheduler` and `seed`
- **THEN** each shows a non-root `Config.User`, `ReadonlyRootfs` true, `CapDrop` ALL, `no-new-privileges`, a `/tmp` tmpfs, and non-zero `NanoCpus` and `Memory`

#### Scenario: Writes outside tmp are refused
- **WHEN** `worker` tries to create a file under `/app`
- **THEN** the write fails with a read-only error

### Requirement: Clean stop
`worker` SHALL have a stop grace period longer than its shutdown deadline plus the time it needs to requeue, so a stop never ends in SIGKILL.

#### Scenario: Grace covers the deadline
- **WHEN** the model is read with the stack's `SCRAPER_SHUTDOWN_DEADLINE`
- **THEN** `stop_grace_period` is at least that deadline plus 10 seconds plus 10 seconds of margin

#### Scenario: Stop of an idle worker
- **WHEN** `docker compose stop worker` runs on a healthy stack
- **THEN** the container exits 0 well before the grace period ends

### Requirement: Audited supply chain
The scraper's pinned dependencies SHALL be scanned with `pip-audit` and the result reported in the PR body's "Security scans" section (ADR 0209, decision 2), while `.docs/security-audit.md` keeps a scraper container section with the container's credentials, networks and hardening.

#### Scenario: Audit recorded
- **WHEN** the change is ready for review
- **THEN** the PR body's "Security scans" section has the `pip-audit -r scraper/requirements.txt -r scraper/requirements-dev.txt` command, its version and its result with no unresolved finding, and `.docs/security-audit.md` has a scraper container section whose claims match `scraper/compose.yaml`
