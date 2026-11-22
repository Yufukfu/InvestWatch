# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose |
|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM |
| [`web/`](web/) | dashboard |
| [`infra/`](infra/) | shared infrastructure: Postgres, Redis, object storage (MinIO), optional Ollama, HTTPS gateway |
| [`contracts/`](contracts/) | data contracts (JSON Schema, OpenAPI), mocks, validator – draft v1 |
| [`.docs/`](.docs/) | project documentation (English): plans, decisions, AI work log |
| [`doc/`](doc/) | UKNF challenge materials (Polish), removed before hand-in |

Who owns which folder: [`.github/CODEOWNERS`](.github/CODEOWNERS) (GitHub requests their review automatically; shared folders have no owner).

## Documentation

- [Integration plan](.docs/integration-plan.md) and [analytics plan](.docs/analytics-plan.md): drafts, contracts not yet confirmed
- [AI-assisted development log](.docs/ai-workflow.md)

## Quick Start

Requires Docker with Compose v2.20+.

```bash
./scripts/init-env.sh          # creates .env with random secrets (never committed)
docker compose up --build      # postgres, redis, minio (bucket iw-raw), gateway, web
docker compose --profile llm up -d   # optional: local Gemma (gemma3:4b via Ollama, several GB download)
```

The LLM is a hosted OpenAI-compatible model by default (a mentor-approved exception to the on-premise rule, [ADR 0304](.docs/decisions/0304-llm-serving.md)); the `llm` profile is the local open-model fallback. Infrastructure, networks and the joining contract for new modules: [`infra/README.md`](infra/README.md).

Open https://localhost:8443 (local certificate: see [`infra/README.md`](infra/README.md)). Until `api` exists the dashboard shows "Brak połączenia z API"; for UI work without it, run the contract mock server and point `API_UPSTREAM` at it, or use `npm run dev` in `web/` against it ([`contracts/README.md`](contracts/README.md), "Mock server"; [`web/README.md`](web/README.md)).

## Hardware requirements

x86-64 or arm64 host with Docker. No GPU: compose declares no GPU device, so Ollama runs on CPU.

| | Default stack | With `--profile llm` |
|---|---|---|
| RAM for Docker, minimum | 6 GB | 12 GB |
| RAM for Docker, recommended | 8 GB | 16 GB |
| CPU cores, minimum / recommended | 4 / 8 | 6 / 12 |
| Free disk, minimum | 10 GB | 22 GB |

How the numbers were obtained (origin/main `ba32bd27`, 2026-11-22):

- **RAM.** The sum of `deploy.resources.limits.memory` in `docker compose --profile llm config`: the 10 long-running services of the default stack are capped at 4.4 GiB together (`renderer` 1 GiB, `worker` 768 MiB, `postgres`, `minio`, `analytics` 512 MiB each, `api` 384 MiB, `redis`, `scheduler` 256 MiB each, `gateway`, `web` 128 MiB each). The one-shot jobs (`minio-init`, `api-migrate`, `seed`, `analytics-eval`) add up to 768 MiB while they start the stack. `ollama` is capped at 6 GiB, `ollama-pull` (one-shot) at 2 GiB. Minimum = limits plus ~1.5 GB for the OS; recommended leaves headroom on top. Measured idle (`docker stats`, part of the stack started, no scraping): `renderer` 230 MiB, `postgres` 27-28 MiB, `redis` 26 MiB, `minio` 26 MiB, `gateway` 16-23 MiB, `web` 8 MiB, far below the caps.
- **CPU.** The sum of the CPU limits: 8.5 for the default stack, `ollama` adds 4.0. The services rarely peak at the same time, hence the lower minimum.
- **Disk, default stack.** `docker image ls` after `docker compose build` on arm64: `renderer` 954 MB (Chromium), `api` 267 MB, `scraper` 250 MB, `analytics` 250 MB, `web` 55 MB, `postgres` 291 MB, `minio` 160 MB, `redis` 119 MB, `caddy` 63 MB: 2.4 GB. The build stages pull `node:22-alpine` (164 MB) and `python:3.13-slim` (144 MB) and leave build cache. Data volumes start empty and grow with scraped pages and screenshots.
- **Disk, `llm` profile.** Ollama image: 2.9 GB compressed on arm64, 3.4 GB on amd64 (sum of layer sizes in the registry manifest of the pinned digest; unpacked it is larger). Models, from the published manifests on `registry.ollama.ai`: `gemma3:4b` 3.35 GB, `bge-m3` 1.16 GB ([#65](https://github.com/Yufukfu/InvestWatch/issues/65)). Both stay loaded at once (`OLLAMA_MAX_LOADED_MODELS=2`), so their 4.5 GB of weights plus the context cache sit inside the 6 GiB `ollama` limit.
- **Speed on CPU** ([`analytics/.env.example`](analytics/.env.example)): warm `bge-m3` took 4-12 s per document on a loaded 16-core CPU, a cold load 37 s.

## Configuration

All settings are environment variables in the root `.env` (template: [`.env.example`](.env.example), secrets from `./scripts/init-env.sh`). Each module's `compose.yaml` passes these to its containers; an empty or missing value takes the default shown in the reference.

| Service (compose file) | Variables from the root `.env` | Reference |
|---|---|---|
| built images (`api`, `analytics`, `scraper`, `renderer`, `web`) | `COMPOSE_PROJECT_NAME`, `IW_VERSION` (image tag); `LOG_LEVEL` (default `INFO`) for `api`, `analytics`, `scraper` | [`web/compose.yaml`](web/compose.yaml) |
| `postgres` ([`infra/`](infra/compose.yaml)) | `POSTGRES_DB`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` | [`infra/README.md`](infra/README.md) |
| `redis` | `REDIS_PASSWORD` | [`infra/README.md`](infra/README.md) |
| `minio`, `minio-init` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | [`infra/README.md`](infra/README.md) |
| `gateway` | `IW_HOSTNAME`, `IW_HTTPS_PORT`, `IW_HTTP_PORT`, `IW_HSTS`, `API_UPSTREAM`, `WEB_UPSTREAM` | [`infra/README.md`](infra/README.md) |
| `ollama`, `ollama-pull` (profile `llm`) | `OLLAMA_MODELS`, `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_KEEP_ALIVE` | [`infra/README.md`](infra/README.md) |
| dev ports overlay ([`infra/compose.dev-ports.yaml`](infra/compose.dev-ports.yaml)) | `IW_DEV_PG_PORT`, `IW_DEV_REDIS_PORT`, `IW_DEV_MINIO_PORT` | [`infra/README.md`](infra/README.md) |
| `api-migrate`, `api` ([`api/`](api/compose.yaml)) | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`, `API_CORS_ORIGINS`; compose derives `DATABASE_URL`, `REDIS_URL` and `CORS_ORIGINS` from these, so never set them, and the image fixes `CONTRACTS_DIR` | [`api/README.md`](api/README.md) |
| `analytics`, `analytics-eval` ([`analytics/`](analytics/compose.yaml)) | `POSTGRES_*`, `REDIS_PASSWORD`; LLM: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_S`, `LLM_DOC_BUDGET_S`, `LLM_CHUNK_CHARS`, `LLM_MAX_CHUNKS`, `LLM_CACHE_TTL_S`, `LLM_BREAKER_FAILURES`, `LLM_BREAKER_COOLDOWN_S`; embeddings: `EMBED_BASE_URL`, `EMBED_MODEL`, `EMBED_API_KEY`, `EMBED_DIM`, `EMBED_TIMEOUT_S`, `EMBED_MAX_CHARS`, `EMBED_CACHE_TTL_S`, `EMBED_BREAKER_FAILURES`, `EMBED_BREAKER_COOLDOWN_S`; gate and near-duplicates: `GATE_ENABLED`, `GATE_SIM_THRESHOLD`, `NEARDUP_NUM_PERM`, `NEARDUP_BANDS`, `NEARDUP_THRESHOLD`, `NEARDUP_MAX_CHARS`, `NEARDUP_TTL_S`; `CLAIM_MIN_IDLE_MS`, `REGISTRY_CSV` | [`analytics/README.md`](analytics/README.md), [`analytics/.env.example`](analytics/.env.example) |
| `seed`, `worker`, `scheduler` ([`scraper/`](scraper/compose.yaml)) | `POSTGRES_*`, `REDIS_PASSWORD`, `MINIO_*`, `SCRAPER_SEED_CRON`, `SCRAPER_SHUTDOWN_DEADLINE`, `SCRAPER_HEALTH_PORT`, `PROXY_LIST`, `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `DOMAIN_MIN_INTERVAL_SECONDS`, `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES`, `ALLOWED_PORTS`, `COMPOSE_INTERNAL_HOSTS`, `FETCH_EXTRA_HOSTS`, `SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR`, `SCRAPER_ATTEMPT_TIMEOUT`, `RENDER_TIMEOUT_SECONDS` | [`scraper/README.md`](scraper/README.md), [`scraper/.env.example`](scraper/.env.example) |
| `renderer` ([`scraper/compose.renderer.yaml`](scraper/compose.renderer.yaml)) | `RENDER_TIMEOUT_SECONDS`, `RENDER_MAX_PAGE_HEIGHT`, `RENDER_MAX_PNG_BYTES`, `RENDER_CONCURRENCY` | [`scraper/README.md`](scraper/README.md) |
| `web` ([`web/`](web/compose.yaml)) | none at runtime. Build time, `npm run build`/`dev` only: `VITE_API_BASE_URL`, `VITE_EVENTS_URL`, `API_PROXY_TARGET` | [`web/README.md`](web/README.md), [`web/.env.example`](web/.env.example) |

The code also reads variables that compose does not forward, so in the stack they keep their defaults; to change one, add it to the service's `environment:` in its `compose.yaml`:

- analytics: `OFFICIAL_SOURCE_DOMAINS`, `WORKER_CONSUMER`, `STREAM_BLOCK_MS`, `MAX_DELIVERIES`, `MAX_DOCUMENT_BYTES`.
- scraper: `SOCIAL_MAX_POSTS`, `SCRAPER_CONSUMER` and the queue and worker settings `SCRAPER_MAX_TRIES`, `SCRAPER_BACKOFF_BASE`, `SCRAPER_BACKOFF_CAP`, `SCRAPER_MAX_RETRY_AFTER`, `SCRAPER_DOMAIN_CONCURRENCY`, `SCRAPER_LEASE_TTL`, `SCRAPER_REQUEUE_DELAY`, `SCRAPER_FAILURE_THRESHOLD`, `SCRAPER_DOMAIN_COOLDOWN`, `SCRAPER_MAX_REQUEUES`, `SCRAPER_MAX_JOBS`, `SCRAPER_RECONNECT_BASE`, `SCRAPER_RECONNECT_CAP`, `SCRAPER_POLL_DELAY`, `SCRAPER_CLAIM_IDLE`, `SCRAPER_TICK_INTERVAL`, `SCRAPER_SWEEP_INTERVAL`, `SCRAPER_CONSUMER_BLOCK`, `SCRAPER_HEALTH_HOST` (meanings: [`scraper/.env.example`](scraper/.env.example)).
- renderer: `RENDER_MAX_BLOCKS`.
- api: `API_HOST`, `API_PORT`.

Compose fixes `RENDERER_URL` (scraper) and `RENDERER_PORT` (renderer) to `http://renderer:8080` and `8080`. Variables for tests only (`TEST_DATABASE_URL`, `TEST_REDIS_URL`, `MOCK_*`) are described in each module's README.

## Licences of third-party services

All run unmodified, each as its own container; InvestWatch code links to none of them.

- **PostgreSQL 17**: PostgreSQL Licence (permissive). [postgresql.org/about/licence](https://www.postgresql.org/about/licence/)
- **Caddy 2** (gateway): Apache-2.0. [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE)
- **Redis 8**: used under its AGPLv3 option (also offered under RSALv2 and SSPLv1). [redis.io/legal/licenses](https://redis.io/legal/licenses/)
- **MinIO** (object storage): AGPL-3.0-or-later, built from source by Chainguard because upstream stopped publishing images ([ADR 0306](.docs/decisions/0306-object-storage-image.md)). [github.com/chainguard-forks/minio](https://github.com/chainguard-forks/minio)
- **Ollama** (optional `llm` profile): MIT. [github.com/ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE). The `gemma3:4b` weights it downloads are under the Gemma Terms of Use, not an OSI licence. [ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms)

Each module owns its `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. A new module adds its file to that list.
