# InvestWatch

InvestWatch looks for online investment promotion that breaks UKNF rules. A scraper collects web pages and social media posts, the analytics service checks each one, and a dashboard shows what it found. We built it for the UKNF challenge at HackNation 2026.

The analytics service runs three checks:

- **M1**: ads for a firm from the KNF register published by someone else, for example a finfluencer.
- **M2**: whether a firm's own materials give the risk information UKNF requires (18 rules).
- **M3**: offers that look like investment advice given without a licence.

## Quick Start

You need Docker with Compose v2.20 or newer, and `openssl`.

1. Create `.env` with random passwords. The file stays on your machine and is never committed.
   ```bash
   ./scripts/init-env.sh
   ```
2. Optional: add an LLM to `.env` ([see below](#llm)). Without one, analytics uses its rules only.
3. Start everything:
   ```bash
   docker compose up --build
   ```
4. Open https://localhost:8443. The browser warns about the certificate once, because it comes from Caddy's local CA ([how to trust it](infra/README.md#tls-locally)).

On the first start the scraper scans every source once, so the first findings appear after a few minutes. This command tells you when every module has at least one (exit code 0):

```bash
docker compose run --rm --no-deps -T bootstrap python -m iw_scraper.bootstrap status
```

A restart on the same data does not scan again. For a fresh demo, wipe the data with `docker compose down -v`. To skip the first scan, set `BOOTSTRAP_SCAN=false` in `.env`.

### LLM

We use DeepSeek Flash through its API ([ADR 0318](.docs/decisions/0318-hosted-llm-deepseek-flash.md)). Add this to `.env`:

```bash
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=<DeepSeek API key>
LLM_TIMEOUT_S=60
LLM_DOC_BUDGET_S=90
CLAIM_MIN_IDLE_MS=120000
```

You can run a local model instead, Gemma (`gemma3:4b`) on Ollama. Take the settings from [`analytics/README.md`](analytics/README.md#llm-hosted-deepseek-or-local-ollama) and start with `docker compose --profile llm up --build`. Expect about 8 GB of downloads, and on a CPU a single LLM check takes three minutes or more.

The brief allows only free models and no paid external APIs. The challenge mentors agreed to a hosted model as long as switching to a local one takes nothing more than a change in `.env` ([ADR 0304](.docs/decisions/0304-llm-serving.md)).

## Hardware requirements

Any x86-64 or arm64 machine with Docker. You don't need a GPU; Ollama runs on the CPU.

| | Default stack | With `--profile llm` |
|---|---|---|
| RAM for Docker, minimum | 6 GB | 12 GB |
| RAM for Docker, recommended | 8 GB | 16 GB |
| CPU cores, minimum / recommended | 4 / 8 | 6 / 12 |
| Free disk, minimum | 10 GB | 22 GB |

The RAM minimum is the most the containers are allowed to use (their memory limits in compose) plus about 1.5 GB for the system. Where the numbers come from: [`infra/README.md`](infra/README.md#resource-sizing).

## Configuration

Everything is set in one file, `.env` in the repository root. `init-env.sh` creates it from [`.env.example`](.env.example), where comments explain the settings. An empty value means the service uses its default. Leave the generated passwords as they are.

Things you may want to change:

| What | Variables |
|---|---|
| LLM | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` and the limits ([LLM](#llm)) |
| Local embeddings (with `--profile llm`) | `EMBED_BASE_URL` |
| Dashboard address | `IW_HOSTNAME`, `IW_HTTPS_PORT`, `IW_HTTP_PORT` |
| First scan and schedule | `BOOTSTRAP_SCAN`, `SCRAPER_SEED_CRON` |
| Proxies | `PROXY_LIST` |
| X and YouTube | `X_AUTH_TOKEN` and `X_CT0` (cookies of an X account), `YT_TRANSCRIPT_PROXY` |

The services and what you can configure in each:

| Service | Role | What you can configure | Details |
|---|---|---|---|
| `gateway` | Caddy, the only entry point, HTTPS | hostname, ports, HSTS | [`infra/README.md`](infra/README.md) |
| `postgres` | database | database name, users, passwords | [`infra/README.md`](infra/README.md) |
| `redis` | queues, live events, alert thresholds | password | [`infra/README.md`](infra/README.md) |
| `minio` | object storage for scraped HTML and screenshots | users, bucket | [`infra/README.md`](infra/README.md) |
| `ollama` (profile `llm`) | local LLM and embeddings | models, context length, how long models stay loaded | [`infra/README.md`](infra/README.md) |
| `api` | REST API and live updates for the dashboard | allowed CORS origins | [`api/README.md`](api/README.md) |
| `analytics` | checks M1–M3 | LLM, embeddings, topic filter, near-duplicate detection | [`analytics/README.md`](analytics/README.md) |
| `worker`, `scheduler`, `seed`, `bootstrap` | scraping | schedule, first scan, proxies, fetch limits, rendering, X and YouTube | [`scraper/README.md`](scraper/README.md) |
| `renderer` | headless Chromium: renders pages and takes screenshots | timeouts, page and image size | [`scraper/README.md`](scraper/README.md) |
| `web` | dashboard | nothing at runtime | [`web/README.md`](web/README.md) |

<details>
<summary>Every variable, by service</summary>

| Service | Variables |
|---|---|
| all built images | `COMPOSE_PROJECT_NAME`, `IW_VERSION` (image tag); `LOG_LEVEL` (default `INFO`) for `api`, `analytics`, `scraper` |
| `postgres` | `POSTGRES_DB`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` |
| `redis` | `REDIS_PASSWORD` |
| `minio`, `minio-init` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| `gateway` | `IW_HOSTNAME`, `IW_HTTPS_PORT`, `IW_HTTP_PORT`, `IW_HSTS`, `API_UPSTREAM`, `WEB_UPSTREAM` |
| `ollama`, `ollama-pull` | `OLLAMA_PULL_MODELS`, `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_KEEP_ALIVE` |
| dev ports ([`infra/compose.dev-ports.yaml`](infra/compose.dev-ports.yaml)) | `IW_DEV_PG_PORT`, `IW_DEV_REDIS_PORT`, `IW_DEV_MINIO_PORT` |
| `api-migrate`, `api` | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`, `API_CORS_ORIGINS` |
| `analytics`: worker | `POSTGRES_*`, `REDIS_PASSWORD`, `CLAIM_MIN_IDLE_MS`, `REGISTRY_CSV` |
| `analytics`: LLM | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_S`, `LLM_DOC_BUDGET_S`, `LLM_CHUNK_CHARS`, `LLM_MAX_CHUNKS`, `LLM_CACHE_TTL_S`, `LLM_BREAKER_FAILURES`, `LLM_BREAKER_COOLDOWN_S` |
| `analytics`: embeddings | `EMBED_BASE_URL`, `EMBED_MODEL`, `EMBED_API_KEY`, `EMBED_DIM`, `EMBED_TIMEOUT_S`, `EMBED_MAX_CHARS`, `EMBED_CACHE_TTL_S`, `EMBED_BREAKER_FAILURES`, `EMBED_BREAKER_COOLDOWN_S` |
| `analytics`: topic filter, near-duplicates | `GATE_ENABLED`, `GATE_EMBED_MIN_MARGIN`, `GATE_EMBED_MIN_CHARS`, `NEARDUP_NUM_PERM`, `NEARDUP_BANDS`, `NEARDUP_THRESHOLD`, `NEARDUP_MAX_CHARS`, `NEARDUP_TTL_S` |
| `analytics-eval` | `POSTGRES_*` |
| `seed`, `bootstrap` | `POSTGRES_*`, `REDIS_PASSWORD`, `SCRAPER_SEED_CRON`, `BOOTSTRAP_SCAN` |
| `worker`, `scheduler` | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_*`, `SCRAPER_SHUTDOWN_DEADLINE` |
| `worker`: fetching | `PROXY_LIST`, `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `DOMAIN_MIN_INTERVAL_SECONDS`, `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES`, `ALLOWED_PORTS`, `COMPOSE_INTERNAL_HOSTS`, `FETCH_EXTRA_HOSTS`, `SCRAPER_ATTEMPT_TIMEOUT`, `SCRAPER_HEALTH_PORT` |
| `worker`: rendering | `SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR`, `RENDER_TIMEOUT_SECONDS` |
| `worker`: X and YouTube | `X_AUTH_TOKEN`, `X_CT0`, `YT_TRANSCRIPT_PROXY`, `YOUTUBE_MAX_VIDEOS` |
| `renderer` | `RENDER_TIMEOUT_SECONDS`, `RENDER_MAX_PAGE_HEIGHT`, `RENDER_MAX_PNG_BYTES`, `RENDER_CONCURRENCY` |
| `web` | build time only (`npm run build` or `dev`): `VITE_API_BASE_URL`, `VITE_EVENTS_URL`, `API_PROXY_TARGET` |

Don't set `DATABASE_URL`, `REDIS_URL` or `CORS_ORIGINS`: compose builds them from the values above. Compose also sets `RENDERER_URL` (`http://renderer:8080`) and `RENDERER_PORT` (`8080`), and the `api` image sets `CONTRACTS_DIR`.

The code reads a few more variables that compose does not pass on, so in the stack they keep their defaults. To change one, add it to `environment:` of that service in its `compose.yaml`:

- analytics: `OFFICIAL_SOURCE_DOMAINS`, `WORKER_CONSUMER`, `STREAM_BLOCK_MS`, `MAX_DELIVERIES`, `MAX_DOCUMENT_BYTES`.
- scraper: `SOCIAL_MAX_POSTS`, `SCRAPER_CONSUMER`, `SCRAPER_MAX_TRIES`, `SCRAPER_BACKOFF_BASE`, `SCRAPER_BACKOFF_CAP`, `SCRAPER_MAX_RETRY_AFTER`, `SCRAPER_DOMAIN_CONCURRENCY`, `SCRAPER_LEASE_TTL`, `SCRAPER_REQUEUE_DELAY`, `SCRAPER_FAILURE_THRESHOLD`, `SCRAPER_DOMAIN_COOLDOWN`, `SCRAPER_MAX_REQUEUES`, `SCRAPER_MAX_JOBS`, `SCRAPER_RECONNECT_BASE`, `SCRAPER_RECONNECT_CAP`, `SCRAPER_POLL_DELAY`, `SCRAPER_CLAIM_IDLE`, `SCRAPER_TICK_INTERVAL`, `SCRAPER_SWEEP_INTERVAL`, `SCRAPER_CONSUMER_BLOCK`, `SCRAPER_HEALTH_HOST` (explained in [`scraper/.env.example`](scraper/.env.example)).
- renderer: `RENDER_MAX_BLOCKS`.
- api: `API_HOST`, `API_PORT`.

Variables used only by tests (`TEST_DATABASE_URL`, `TEST_REDIS_URL`, `MOCK_*`) are described in each module's README.

</details>

## Repository structure

| Folder | Contents |
|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler |
| [`analytics/`](analytics/) | checks M1–M3, KNF firm register, LLM |
| [`api/`](api/) | database schema, REST API, live events |
| [`web/`](web/) | dashboard |
| [`infra/`](infra/) | Postgres, Redis, object storage (MinIO), optional Ollama, HTTPS gateway |
| [`contracts/`](contracts/) | data contracts v1 (JSON Schema, OpenAPI), mocks, validator |
| [`.docs/`](.docs/) | plans, decisions (ADRs), log of how we worked with AI |

Each module has its own `compose.yaml`, and the root [`compose.yaml`](compose.yaml) just includes them all.

More documentation:

- Architecture and data contracts: [integration plan](.docs/integration-plan.md)
- How the checks work: [analytics plan](.docs/analytics-plan.md)
- Running more `worker` and `analytics` instances: [`infra/README.md`](infra/README.md#scale-out)
- How we worked with AI: [`.docs/ai-workflow.md`](.docs/ai-workflow.md)

## Licences of third-party services

Each one runs unmodified in its own container, and InvestWatch code does not link to any of them.

- **PostgreSQL 17**: PostgreSQL Licence (permissive). [postgresql.org/about/licence](https://www.postgresql.org/about/licence/)
- **Caddy 2** (gateway): Apache-2.0. [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE)
- **Redis 8**: used under its AGPLv3 option (it is also offered under RSALv2 and SSPLv1). [redis.io/legal/licenses](https://redis.io/legal/licenses/)
- **MinIO** (object storage): AGPL-3.0-or-later. Chainguard builds it from source, because upstream stopped publishing images ([ADR 0306](.docs/decisions/0306-object-storage-image.md)). [github.com/chainguard-forks/minio](https://github.com/chainguard-forks/minio)
- **Ollama** (optional, profile `llm`): MIT. [github.com/ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE). Of the models it downloads, `gemma3:4b` is under the Gemma Terms of Use, which is not an OSI licence ([ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms)), and `bge-m3` is under MIT ([ADR 0313](.docs/decisions/0313-embeddings-model-and-serving.md)).
