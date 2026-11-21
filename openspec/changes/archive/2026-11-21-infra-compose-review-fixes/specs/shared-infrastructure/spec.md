# Spec Delta

## Purpose
Review fixes to the shared infrastructure from PR #18: idempotent secret bootstrap with hosted-LLM slots, and smoke checks that can fail.

## MODIFIED Requirements

### Requirement: Object storage with bucket iw-raw
The stack SHALL run an S3-compatible object store as service `minio` with a named volume and a healthcheck. A one-shot `minio-init` SHALL create the private bucket `iw-raw` and an app user whose policy allows object read, write, delete and list on `iw-raw` only, and SHALL exit 0. Re-running `minio-init` on an existing volume SHALL succeed without changing existing objects, and SHALL set anonymous access on the bucket back to none.

#### Scenario: Bucket exists after start
- **WHEN** `docker compose up` has finished and `minio-init` has exited
- **THEN** `minio-init` exited with code 0 and bucket `iw-raw` exists

#### Scenario: App credentials are limited to the bucket
- **WHEN** a client uses the app credentials (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`) to put and get `html/<uuid>.html` in `iw-raw`, and then to create another bucket
- **THEN** the put and get succeed and the bucket creation is denied

#### Scenario: Bucket is not public
- **WHEN** an object in `iw-raw` is requested without credentials
- **THEN** the request is denied

#### Scenario: Init is idempotent
- **WHEN** `docker compose up` runs a second time on the same volume after an object was stored
- **THEN** `minio-init` exits 0 and the object is unchanged

#### Scenario: Init closes a public bucket
- **WHEN** the bucket was made public by hand and `minio-init` runs again
- **THEN** an anonymous GET on an object in `iw-raw` is denied

### Requirement: Secrets only from .env
Every infrastructure password and key SHALL come from the untracked root `.env`, with no default in any compose file. Compose SHALL refuse to start when one is missing, naming the variable. The tracked root `.env.example` SHALL list every variable the shared services and their clients use, with secrets left empty, and `scripts/init-env.sh` SHALL fill every secret (`*_PASSWORD`, `*_SECRET_KEY`) with a random value of at least 32 characters. It SHALL leave every other variable as in `.env.example`, including `LLM_API_KEY`, which the operator sets. Run again on an existing `.env`, it SHALL leave that file untouched and exit 0. Without `openssl` it SHALL fail with a message that names `openssl`.

#### Scenario: Missing Redis password
- **WHEN** `docker compose config` runs with `REDIS_PASSWORD` unset
- **THEN** it fails with an error naming `REDIS_PASSWORD`

#### Scenario: Missing object-store secret
- **WHEN** `docker compose config` runs with `MINIO_ROOT_PASSWORD` or `MINIO_SECRET_KEY` unset
- **THEN** it fails with an error naming the missing variable

#### Scenario: Generated .env is complete
- **WHEN** `scripts/init-env.sh` runs in a clone without `.env`
- **THEN** every secret variable in `.env` has a value of at least 32 characters and `docker compose config` succeeds

#### Scenario: Existing .env is kept
- **WHEN** `scripts/init-env.sh` runs and the target file already exists
- **THEN** the file is unchanged, the script says it already exists, and it exits 0

#### Scenario: Hosted LLM key is not generated
- **WHEN** `scripts/init-env.sh` creates a new `.env`
- **THEN** `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` are present and empty

#### Scenario: openssl missing
- **WHEN** `scripts/init-env.sh` runs without `openssl` on the PATH
- **THEN** it exits non-zero with a message naming `openssl`, and no file is created

### Requirement: Network isolation
Only the gateway SHALL publish host ports in the default stack. `redis`, `minio`, `postgres` and `ollama` SHALL be on `data`, which stays `internal`. Outbound internet SHALL be available only to services on a non-internal network. Those are `egress`, which a module joins for internet access, and `edge`, which carries the gateway's published ports and so cannot be internal; a module joins `edge` only to be routed. The opt-in dev-ports override also gives `postgres`, `redis` and `minio` internet, because they join its non-internal `devhost` network to publish. The opt-in file `infra/compose.dev-ports.yaml` SHALL be the only way to publish Postgres, Redis or the object store on the host, and it SHALL bind to `127.0.0.1` only.

#### Scenario: Default stack publishes only the gateway
- **WHEN** `docker compose up -d` has finished
- **THEN** `docker compose ps --format json` shows published ports for `gateway`, and for no other service

#### Scenario: Data services have no internet
- **WHEN** a container attached only to `data` tries to open a TCP connection to a public address
- **THEN** the connection fails

#### Scenario: Dev ports bind to loopback
- **WHEN** the stack runs with `-f compose.yaml -f infra/compose.dev-ports.yaml`
- **THEN** Postgres, Redis and the object store are reachable on `127.0.0.1` ports and on no other host address
