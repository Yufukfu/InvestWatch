# shared-infrastructure Specification

## Purpose

The shared services every module needs (Redis, object storage, an optional local LLM), started by one `docker compose up` next to Postgres and the gateway from [ADR 0202](../../../.docs/decisions/0202-deployment-topology.md), isolated per stack, and joined by modules through a fixed contract. Network keys are `data`, `edge` and `egress`; Docker names them `<project>_data`, `<project>_edge` and `<project>_egress`. Names and payloads on Redis and in `iw-raw` are those of `.docs/integration-plan.md` §2 and §6 and ADR 0305. They are not restated here.

## Requirements

### Requirement: Redis service
The stack SHALL run a `redis` service that requires a password, persists data with AOF to a named volume, uses `maxmemory-policy noeviction`, reports healthy only when it answers an authenticated `PING`, and is attached only to the internal network `data`.

#### Scenario: Healthy and authenticated
- **WHEN** `docker compose up` has finished and `redis` is healthy
- **THEN** an authenticated `PING` from a container on `data` returns `PONG`, and an unauthenticated command returns `NOAUTH`

#### Scenario: Thresholds survive a restart
- **WHEN** a value is written to `iw:settings:thresholds` and `redis` is restarted with `docker compose restart redis`
- **THEN** the key still holds the same value

#### Scenario: Stream entries are not evicted
- **WHEN** the running `redis` configuration is read with `CONFIG GET maxmemory-policy` and `CONFIG GET appendonly`
- **THEN** they return `noeviction` and `yes`

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
Every infrastructure password and key SHALL come from the untracked root `.env`, with no default in any compose file. Compose SHALL refuse to start when one is missing, naming the variable. The tracked root `.env.example` SHALL list every variable the shared services and their clients use, with secrets left empty, and `scripts/init-env.sh` SHALL fill every secret (`*_PASSWORD`, `*_SECRET_KEY`) with a random value of at least 32 characters.

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
- **AND** run again on an existing `.env`, `scripts/init-env.sh` SHALL leave that file untouched and exit 0

#### Scenario: Hosted LLM key is not generated
- **WHEN** `scripts/init-env.sh` creates a new `.env`
- **THEN** `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` are present and empty
- **AND** `scripts/init-env.sh` SHALL leave every variable other than the secrets as in `.env.example`, including `LLM_API_KEY`, which the operator sets

#### Scenario: openssl missing
- **WHEN** `scripts/init-env.sh` runs without `openssl` on the PATH
- **THEN** it exits non-zero with a message naming `openssl`, and no file is created
- **AND** without `openssl`, `scripts/init-env.sh` SHALL fail with a message that names `openssl`

### Requirement: Optional local LLM behind a profile
The stack SHALL define an `ollama` service and a one-shot `ollama-pull` that pulls every model in `OLLAMA_PULL_MODELS` (default `gemma3:4b bge-m3`), both only in the compose profile `llm`. Without the profile, neither SHALL start and no model weights SHALL be downloaded. With the profile, `ollama` SHALL serve the OpenAI-compatible API under `/v1` to containers on `data` at `http://ollama:11434/v1`, and keep the weights in a named volume.

#### Scenario: Plain up downloads no weights
- **WHEN** `docker compose up -d` runs without `--profile llm`
- **THEN** `docker compose ps -a` lists neither `ollama` nor `ollama-pull`, and no `ollama` volume exists

#### Scenario: Profile serves gemma3:4b and bge-m3
- **WHEN** `docker compose --profile llm up -d` has finished and `ollama-pull` has exited 0
- **THEN** `GET http://ollama:11434/v1/models` from a container on `data` lists `gemma3:4b` and `bge-m3`

#### Scenario: Pull fails without network
- **WHEN** the `llm` profile starts and the model registry cannot be reached
- **THEN** `ollama-pull` exits non-zero, and every service outside the profile stays healthy

#### Scenario: Only the pull reaches the internet
- **WHEN** the `llm` profile runs
- **THEN** of `ollama` and `ollama-pull`, only the `ollama-pull` one-shot SHALL reach the internet
- **AND** `ollama` SHALL publish no host port and SHALL NOT join a network with internet access

#### Scenario: Pull list does not set the models directory
- **WHEN** `docker compose --profile llm config` resolves the stack, with `OLLAMA_MODELS="gemma3:4b bge-m3"` left over in the environment
- **THEN** `ollama-pull` has `OLLAMA_PULL_MODELS`, and neither `ollama` nor `ollama-pull` has `OLLAMA_MODELS` (Ollama's own models-directory setting)
- **AND** on an empty model volume `ollama-pull` SHALL exit 0

### Requirement: Network isolation
Only the gateway SHALL publish host ports in the default stack. `redis`, `minio`, `postgres` and `ollama` SHALL be on `data`, which stays `internal`. Outbound internet SHALL be available only to services on a non-internal network. Those are `egress`, which a module joins for internet access, and `edge`, which carries the gateway's published ports and so cannot be internal; a module joins `edge` only to be routed.

#### Scenario: Default stack publishes only the gateway
- **WHEN** `docker compose up -d` has finished
- **THEN** `docker compose ps --format json` shows published ports for `gateway`, and for no other service

#### Scenario: Data services have no internet
- **WHEN** a container attached only to `data` tries to open a TCP connection to a public address
- **THEN** the connection fails

#### Scenario: Dev ports bind to loopback
- **WHEN** the stack runs with `-f compose.yaml -f infra/compose.dev-ports.yaml`
- **THEN** Postgres, Redis and the object store are reachable on `127.0.0.1` ports and on no other host address
- **AND** the opt-in file `infra/compose.dev-ports.yaml` SHALL be the only way to publish Postgres, Redis or the object store on the host, and it SHALL bind to `127.0.0.1` only
- **AND** this override also gives `postgres`, `redis` and `minio` internet, because they join its non-internal `devhost` network to publish

### Requirement: Parallel stacks do not collide
Network names and volumes SHALL be scoped to the compose project, so two stacks started from different worktrees with different `COMPOSE_PROJECT_NAME` and gateway ports (`IW_HTTPS_PORT`, `IW_HTTP_PORT`) run at the same time without sharing a network, a volume or a service DNS name.

#### Scenario: Two worktrees at once
- **WHEN** stack `investwatch` runs on ports 8443/8080 and stack `iw-infra-compose` is started from another worktree on ports 8444/8081
- **THEN** both stacks become healthy, and `docker network ls` shows separate data, edge and egress networks for each project

#### Scenario: No cross-stack DNS
- **WHEN** a container in one stack resolves `redis`
- **THEN** it gets only the address of its own stack's `redis`

### Requirement: Module joining contract
A module SHALL join the stack by adding its own `<module>/compose.yaml` to the root `include:`, attaching to the networks it needs (`data` for Postgres, Redis, object store and Ollama; `edge` to be routed by the gateway; `egress` for internet), and waiting on `postgres` and `redis` with `condition: service_healthy` and on `minio-init` with `condition: service_completed_successfully`. A module's compose file SHALL take infrastructure secrets only from variables defined in the root `.env.example`.

#### Scenario: Module waits for infrastructure
- **WHEN** a module service declares the documented `depends_on` conditions and the stack starts from empty volumes
- **THEN** the module container starts only after `postgres` and `redis` are healthy and `minio-init` has exited 0

#### Scenario: Infrastructure failure blocks dependants
- **WHEN** `minio-init` exits non-zero
- **THEN** `docker compose up` reports the failure and no module service that depends on it is started
