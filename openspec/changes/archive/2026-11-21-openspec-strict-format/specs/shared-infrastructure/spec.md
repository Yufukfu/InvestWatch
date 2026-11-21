## MODIFIED Requirements

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
The stack SHALL define an `ollama` service and a one-shot `ollama-pull` that pulls `gemma3:4b`, both only in the compose profile `llm`. Without the profile, neither SHALL start and no model weights SHALL be downloaded. With the profile, `ollama` SHALL serve the OpenAI-compatible API under `/v1` to containers on `data` at `http://ollama:11434/v1`, keep the weights in a named volume, publish no host port, and SHALL NOT join a network with internet access.

#### Scenario: Plain up downloads no weights
- **WHEN** `docker compose up -d` runs without `--profile llm`
- **THEN** `docker compose ps -a` lists neither `ollama` nor `ollama-pull`, and no `ollama` volume exists

#### Scenario: Profile serves gemma3:4b
- **WHEN** `docker compose --profile llm up -d` has finished and `ollama-pull` has exited 0
- **THEN** `GET http://ollama:11434/v1/models` from a container on `data` lists `gemma3:4b`

#### Scenario: Pull fails without network
- **WHEN** the `llm` profile starts and the model registry cannot be reached
- **THEN** `ollama-pull` exits non-zero, and every service outside the profile stays healthy

#### Scenario: Only the pull reaches the internet
- **WHEN** the `llm` profile runs
- **THEN** of `ollama` and `ollama-pull`, only the `ollama-pull` one-shot SHALL reach the internet

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
