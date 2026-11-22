# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Quick Start

Requires Docker with Compose v2.20 or newer, and `openssl`.

```bash
./scripts/init-env.sh        # creates .env with random passwords; .env is never committed
docker compose up --build    # starts the whole stack
```

Open https://localhost:8443. The certificate comes from Caddy's local CA, so the browser warns once ([how to trust it](infra/README.md#tls-locally)).

The first start scans every scheduled source once. Findings appear after a few minutes; this command exits 0 once every module has one:

```bash
docker compose run --rm --no-deps -T bootstrap python -m iw_scraper.bootstrap status
```

A second `up` on the same volumes does not scan again, so for a clean demo delete the data with `docker compose down -v`. To skip the first scan, set `BOOTSTRAP_SCAN=false` in `.env`.

### LLM

`init-env.sh` leaves the LLM settings empty, and analytics then runs on rules only. To turn the LLM on, add one of the options below to `.env` before `up`.

Hosted DeepSeek Flash, the default ([ADR 0318](.docs/decisions/0318-hosted-llm-deepseek-flash.md)):

```bash
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=<DeepSeek API key>
LLM_TIMEOUT_S=60
LLM_DOC_BUDGET_S=90
CLAIM_MIN_IDLE_MS=120000
```

Local Gemma (`gemma3:4b`) on Ollama: copy the values from [`analytics/README.md`](analytics/README.md#llm-hosted-deepseek-or-local-ollama) and start with `docker compose --profile llm up --build`. This downloads about 8 GB (the Ollama image and two models), and on CPU a single LLM check takes 3 minutes or more.

The challenge mentors approved the hosted model as an exception to the brief's rule of free models and no paid external APIs, on the condition that switching to a local open model needs only `.env` changes ([ADR 0304](.docs/decisions/0304-llm-serving.md)).

## Hardware requirements

An x86-64 or arm64 host. No GPU needed: Ollama runs on CPU.

| | Default stack | With `--profile llm` |
|---|---|---|
| RAM for Docker, minimum | 6 GB | 12 GB |
| RAM for Docker, recommended | 8 GB | 16 GB |
| CPU cores, minimum / recommended | 4 / 8 | 6 / 12 |
| Free disk, minimum | 10 GB | 22 GB |

The RAM minimum is the sum of the memory limits in compose plus about 1.5 GB for the OS. Per-service limits, image and model sizes: [`infra/README.md`](infra/README.md#resource-sizing).

## Configuration

All settings are environment variables in the root `.env`, created from [`.env.example`](.env.example). Each module's `compose.yaml` passes them to its containers. An empty or missing value takes the default given in the reference.

Most runs change only these:

- LLM: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` and their limits ([above](#llm)); `EMBED_BASE_URL` for local embeddings.
- Address: `IW_HOSTNAME`, `IW_HTTPS_PORT`, `IW_HTTP_PORT`.
- Scraping: `BOOTSTRAP_SCAN`, `SCRAPER_SEED_CRON`, `PROXY_LIST`; for the X and YouTube collectors, `X_AUTH_TOKEN` and `X_CT0` (X account cookies) and `YT_TRANSCRIPT_PROXY`.

Every variable, by service:

| Service | Variables | Reference |
|---|---|---|
| all built images | `COMPOSE_PROJECT_NAME`, `IW_VERSION` (image tag); `LOG_LEVEL` (default `INFO`) for `api`, `analytics`, `scraper` | [`.env.example`](.env.example) |
| `postgres` | `POSTGRES_DB`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` | [`infra/README.md`](infra/README.md) |
| `redis` | `REDIS_PASSWORD` | [`infra/README.md`](infra/README.md) |
| `minio`, `minio-init` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | [`infra/README.md`](infra/README.md) |
| `gateway` | `IW_HOSTNAME`, `IW_HTTPS_PORT`, `IW_HTTP_PORT`, `IW_HSTS`, `API_UPSTREAM`, `WEB_UPSTREAM` | [`infra/README.md`](infra/README.md) |
| `ollama`, `ollama-pull` (profile `llm`) | `OLLAMA_PULL_MODELS`, `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_KEEP_ALIVE` | [`infra/README.md`](infra/README.md) |
| dev ports ([`infra/compose.dev-ports.yaml`](infra/compose.dev-ports.yaml)) | `IW_DEV_PG_PORT`, `IW_DEV_REDIS_PORT`, `IW_DEV_MINIO_PORT` | [`infra/README.md`](infra/README.md) |
| `api-migrate`, `api` | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`, `API_CORS_ORIGINS` | [`api/README.md`](api/README.md) |
| `analytics`: worker | `POSTGRES_*`, `REDIS_PASSWORD`, `CLAIM_MIN_IDLE_MS`, `REGISTRY_CSV` | [`analytics/README.md`](analytics/README.md), [`analytics/.env.example`](analytics/.env.example) |
| `analytics`: LLM | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_S`, `LLM_DOC_BUDGET_S`, `LLM_CHUNK_CHARS`, `LLM_MAX_CHUNKS`, `LLM_CACHE_TTL_S`, `LLM_BREAKER_FAILURES`, `LLM_BREAKER_COOLDOWN_S` | same |
| `analytics`: embeddings | `EMBED_BASE_URL`, `EMBED_MODEL`, `EMBED_API_KEY`, `EMBED_DIM`, `EMBED_TIMEOUT_S`, `EMBED_MAX_CHARS`, `EMBED_CACHE_TTL_S`, `EMBED_BREAKER_FAILURES`, `EMBED_BREAKER_COOLDOWN_S` | same |
| `analytics`: topic gate, near-duplicates | `GATE_ENABLED`, `GATE_EMBED_MIN_MARGIN`, `GATE_EMBED_MIN_CHARS`, `NEARDUP_NUM_PERM`, `NEARDUP_BANDS`, `NEARDUP_THRESHOLD`, `NEARDUP_MAX_CHARS`, `NEARDUP_TTL_S` | same |
| `analytics-eval` | `POSTGRES_*` | same |
| `seed`, `bootstrap` | `POSTGRES_*`, `REDIS_PASSWORD`, `SCRAPER_SEED_CRON`, `BOOTSTRAP_SCAN` | [`scraper/README.md`](scraper/README.md), [`scraper/.env.example`](scraper/.env.example) |
| `worker`, `scheduler` | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_*`, `SCRAPER_SHUTDOWN_DEADLINE` | same |
| `worker`: fetching | `PROXY_LIST`, `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `DOMAIN_MIN_INTERVAL_SECONDS`, `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES`, `ALLOWED_PORTS`, `COMPOSE_INTERNAL_HOSTS`, `FETCH_EXTRA_HOSTS`, `SCRAPER_ATTEMPT_TIMEOUT`, `SCRAPER_HEALTH_PORT` | same |
| `worker`: rendering | `SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR`, `RENDER_TIMEOUT_SECONDS` | same |
| `worker`: X and YouTube | `X_AUTH_TOKEN`, `X_CT0`, `YT_TRANSCRIPT_PROXY`, `YOUTUBE_MAX_VIDEOS` | [`scraper/README.md`](scraper/README.md#x-and-youtube) |
| `renderer` ([`scraper/compose.renderer.yaml`](scraper/compose.renderer.yaml)) | `RENDER_TIMEOUT_SECONDS`, `RENDER_MAX_PAGE_HEIGHT`, `RENDER_MAX_PNG_BYTES`, `RENDER_CONCURRENCY` | [`scraper/README.md`](scraper/README.md) |
| `web` | none at runtime; at build time (`npm run build` or `dev`): `VITE_API_BASE_URL`, `VITE_EVENTS_URL`, `API_PROXY_TARGET` | [`web/README.md`](web/README.md), [`web/.env.example`](web/.env.example) |

Compose builds `DATABASE_URL`, `REDIS_URL` and `CORS_ORIGINS` from the values above, so do not set them. It also fixes `RENDERER_URL` to `http://renderer:8080` and `RENDERER_PORT` to `8080`; the `api` image sets `CONTRACTS_DIR`.

Some variables are read by the code but not passed by compose, so in the stack they keep their defaults. To change one, add it to the service's `environment:` in its `compose.yaml`:

- analytics: `OFFICIAL_SOURCE_DOMAINS`, `WORKER_CONSUMER`, `STREAM_BLOCK_MS`, `MAX_DELIVERIES`, `MAX_DOCUMENT_BYTES`.
- scraper: `SOCIAL_MAX_POSTS`, `SCRAPER_CONSUMER`, `SCRAPER_MAX_TRIES`, `SCRAPER_BACKOFF_BASE`, `SCRAPER_BACKOFF_CAP`, `SCRAPER_MAX_RETRY_AFTER`, `SCRAPER_DOMAIN_CONCURRENCY`, `SCRAPER_LEASE_TTL`, `SCRAPER_REQUEUE_DELAY`, `SCRAPER_FAILURE_THRESHOLD`, `SCRAPER_DOMAIN_COOLDOWN`, `SCRAPER_MAX_REQUEUES`, `SCRAPER_MAX_JOBS`, `SCRAPER_RECONNECT_BASE`, `SCRAPER_RECONNECT_CAP`, `SCRAPER_POLL_DELAY`, `SCRAPER_CLAIM_IDLE`, `SCRAPER_TICK_INTERVAL`, `SCRAPER_SWEEP_INTERVAL`, `SCRAPER_CONSUMER_BLOCK`, `SCRAPER_HEALTH_HOST` (meanings in [`scraper/.env.example`](scraper/.env.example)).
- renderer: `RENDER_MAX_BLOCKS`.
- api: `API_HOST`, `API_PORT`.

Test-only variables (`TEST_DATABASE_URL`, `TEST_REDIS_URL`, `MOCK_*`) are in each module's README.

## Repository structure

| Folder | Contents |
|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM |
| [`api/`](api/) | database schema, REST API, live events |
| [`web/`](web/) | dashboard |
| [`infra/`](infra/) | Postgres, Redis, object storage (MinIO), optional Ollama, HTTPS gateway |
| [`contracts/`](contracts/) | data contracts v1 (JSON Schema, OpenAPI), mocks, validator |
| [`.docs/`](.docs/) | plans, decisions (ADRs), AI-assisted development log |

Each module has its own `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. Architecture and contracts: [integration plan](.docs/integration-plan.md). Analytics modules: [analytics plan](.docs/analytics-plan.md). Running more `worker` and `analytics` instances: [`infra/README.md`](infra/README.md#scale-out). How the team worked with AI: [`.docs/ai-workflow.md`](.docs/ai-workflow.md).

## Licences of third-party services

Each runs unmodified in its own container, and InvestWatch code does not link to any of them.

- **PostgreSQL 17**: PostgreSQL Licence (permissive). [postgresql.org/about/licence](https://www.postgresql.org/about/licence/)
- **Caddy 2** (gateway): Apache-2.0. [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE)
- **Redis 8**: used under its AGPLv3 option (also offered under RSALv2 and SSPLv1). [redis.io/legal/licenses](https://redis.io/legal/licenses/)
- **MinIO** (object storage): AGPL-3.0-or-later, built from source by Chainguard because upstream stopped publishing images ([ADR 0306](.docs/decisions/0306-object-storage-image.md)). [github.com/chainguard-forks/minio](https://github.com/chainguard-forks/minio)
- **Ollama** (optional `llm` profile): MIT. [github.com/ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE). Of the models it downloads, `gemma3:4b` is under the Gemma Terms of Use, not an OSI licence ([ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms)), and `bge-m3` is under MIT ([ADR 0313](.docs/decisions/0313-embeddings-model-and-serving.md)).
