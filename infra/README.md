# infra

Infrastructure shared by every module (owners: [`.github/CODEOWNERS`](../.github/CODEOWNERS)). Each module has its own `compose.yaml`; the root `compose.yaml` only includes them, so a module is deployed, scaled or replaced without touching the others. Reasoning: [ADR 0202](../.docs/decisions/0202-deployment-topology.md) (topology), [ADR 0306](../.docs/decisions/0306-object-storage-image.md) (object storage and Redis images), [ADR 0304](../.docs/decisions/0304-llm-serving.md) (LLM fallback).

| Service | Purpose | Reachable from |
|---|---|---|
| `postgres` | PostgreSQL 17 | network `data` only (internal: no host port, no internet). Local: `docker compose exec postgres psql -U iw_admin -d investwatch` |
| `redis` | Redis 8: stream `iw:documents`, pub/sub `iw:events`, key `iw:settings:thresholds`. AOF on, `noeviction`, password required | `data` only. Local: `docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli'` |
| `minio` | S3-compatible object storage (MinIO, Chainguard build), bucket `iw-raw` | `data` only, console off |
| `minio-init` | one-shot: creates the private bucket `iw-raw` and the app user limited to it, then exits 0 | runs on every `up`, idempotent |
| `ollama` | local LLM fallback `gemma3:4b`, **only with `--profile llm`** | `data` only (`http://ollama:11434/v1`): its API has no auth, so it gets no internet |
| `ollama-pull` | one-shot, profile `llm`: its own loopback-only server pulls the model into the shared volume, then exits | `egress` only |
| `gateway` | Caddy: the only public entry, TLS, `/api` + `/socket.io` → `api:8000`, `/` → `web:8080` | host `https://localhost:8443` (HTTP 8080 redirects) |

## Networks

Keys `data`, `edge` and `egress`. Compose names them per project (`<project>_data`, ...), so stacks from parallel worktrees never share a network or a DNS name.

| Network | Internal | Join it to |
|---|---|---|
| `data` | yes | reach Postgres, Redis, object storage, Ollama |
| `edge` | no (the gateway publishes through it) | be routed by the gateway (`api`, `web`) |
| `egress` | no | reach the internet (scraper, analytics' hosted LLM) |

## Joining the stack (scraper, analytics, api)

A module adds `<module>/compose.yaml` with its own Dockerfile, and one line in the root `include:`. Declare the networks you use with the same keys and settings, **without `name:`**, and wait for the infrastructure:

```yaml
services:
  analytics:
    build: .
    networks: [data, egress]          # + edge if the gateway routes to it
    environment:
      DATABASE_URL: postgresql://${POSTGRES_APP_USER:-iw_app}:${POSTGRES_APP_PASSWORD:?}@postgres:5432/${POSTGRES_DB:-investwatch}
      REDIS_URL: redis://:${REDIS_PASSWORD:?}@redis:6379/0
      MINIO_ENDPOINT: ${MINIO_ENDPOINT:-minio:9000}
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-iw-app}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:?}
      MINIO_BUCKET: ${MINIO_BUCKET:-iw-raw}
      MINIO_SECURE: ${MINIO_SECURE:-false}
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      minio-init: { condition: service_completed_successfully }
networks:
  data: { internal: true }
  egress: {}
  edge: {}
```

- Infrastructure secrets come only from variables in the root `.env.example`. Never use the MinIO root user or `iw_admin` in a service, except a migration step (Alembic in `api`, [ADR 0303](../.docs/decisions/0303-database-schema-ownership.md)).
- Runtime setup belongs to the consumer: analytics creates its consumer group (`XGROUP CREATE iw:documents analytics $ MKSTREAM`), and `api` writes the default thresholds ([ADR 0305](../.docs/decisions/0305-threshold-storage.md)). The scraper's job queue uses the same Redis, db 0, keys prefixed `iw:scraper:`.
- Redis runs `noeviction` with `maxmemory 128mb`: when it is full, every write fails instead of silently dropping data. The scraper therefore caps the stream when it publishes: `XADD iw:documents MAXLEN ~ 10000 * document_id <uuid> schema v1` (approximate trimming is cheap; 10 000 is an example, sized so unconsumed entries stay far below the cap). Analytics acknowledges entries (`XACK`) as it processes them.
- Local LLM: `LLM_BASE_URL=http://ollama:11434/v1`, `LLM_MODEL=gemma3:4b`, `LLM_API_KEY=ollama` (any non-empty value).
- Running one module alone joins the same networks only with the stack's project name: `docker compose -p investwatch --env-file .env -f web/compose.yaml up`.

## Scale-out

On one host, `worker` (scraper) and `analytics` scale with `--scale`. Repeat the flags on every `up`: a plain `up` returns each service to one replica.

```bash
docker compose up -d --wait --scale worker=3 --scale analytics=2     # start
docker compose ps worker analytics                                    # the replicas
docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli XINFO CONSUMERS iw:documents analytics'
for c in $(docker compose ps -q analytics); do echo "$(docker inspect -f '{{.Config.Hostname}}' $c): $(docker logs $c 2>&1 | grep -c 'message handled') documents"; done
docker compose up -d --wait --scale worker=1 --scale analytics=1     # back to one each
```

The consumer list also keeps the names of replicas that were stopped or replaced; compare it with `docker compose ps`. A killed replica's unacknowledged entries are claimed by another one after `CLAIM_MIN_IDLE_MS` (60 s).

| Service | Scale? | Why (evidence: `openspec/changes/archive/2026-11-22-architecture-scale-out/evidence.md`, 2026-11-22) |
|---|---|---|
| `worker` | **yes** | Run with 3. Jobs, run locks and per-domain limits live in Redis, so replicas share the queue and, by code reading, keep the politeness limits (a run with 3 workers on the 4 Telegram sources is consistent with the 5 s rule, 4.9 / 15.0 / 5.0 s between logged fetches, but those are response times, not request starts). Speed-up is bounded by those limits: one domain is still fetched at most every 5 s, wherever it runs. |
| `analytics` | **yes** | Run with 2: each replica is its own consumer of `iw:documents` (name = container hostname), 223 documents split 111/112 with no overlap and no duplicate finding. 892 re-announced entries drained in 21-24 s with one replica and 9-10 s with two (rules-only, 12 CPU machine, same input). Two caveats: with the hosted LLM every replica adds its own concurrent calls and its own circuit breaker, and the local `ollama` is one instance, so replicas add no LLM throughput; two near-duplicate documents handled in the same moment by different replicas can each start a group (`neardup.py` reads, then writes), so one alert may appear twice instead of merged. |
| `scheduler` | no | Exactly one is the design. Started twice by mistake it is harmless: the job id is source plus slot, so a slot is enqueued once (code, not run across a cron slot). |
| `api` | no | Run with 2: the gateway sent all 30 requests to one replica (Caddy dials the name `api` and takes one of the two addresses), so the second replica idles. Balancing it would need dynamic upstreams and Socket.IO session stickiness; not done. |
| `web` | no | Not run with replicas; it goes through the same gateway upstream rule as `api`, so extra replicas would idle. |
| `gateway` | no | Publishes the host ports: a second replica fails with "port is already allocated". |
| `renderer` | no | Optional, off by default, not run with replicas. |
| `postgres`, `redis`, `minio` | no | Single-node data stores, no clustering configured. |
| `ollama` | no | Profile `llm`, one model server (4 CPUs, 6 GB). |
| `api-migrate`, `minio-init`, `seed`, `analytics-eval`, `ollama-pull` | n/a | One-shots that exit; not services to scale. |

`infra/tests/smoke.sh scale` starts two `worker` and two `analytics` replicas on a throwaway project and checks that both run and that each analytics replica is a consumer. The compose limits add up to 5 CPUs and 3.3 GB for `worker=3 analytics=2`, on top of the single-instance stack.

## Database access

- `iw_admin` (from `POSTGRES_ADMIN_*`): migrations and ops only.
- `iw_app` (from `POSTGRES_APP_*`): what services use. CRUD on tables in `public`, no DDL, no superuser.
- Connection for services on `data`: `postgresql://iw_app:<password>@postgres:5432/investwatch`.
- Schema comes from migrations (Alembic in `api`), never by hand. Run migrations as `iw_admin`: `iw_app` gets CRUD automatically only on tables created by `iw_admin`. The init script runs only on an empty volume; to reset: `docker compose down -v`.

## Object storage access

- Root user (`MINIO_ROOT_*`): `minio-init` only.
- App user (`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`): read, write, delete and list objects in `iw-raw`; no other bucket, no admin. Anonymous access is off.
- Keys: `html/{document_id}.html`, `shot/{document_id}/{viewport}.png`, `media/{document_id}/{n}.{ext}` ([integration-plan.md](../.docs/integration-plan.md) §2).

## Local LLM (optional)

```bash
docker compose --profile llm up -d          # adds ollama and pulls gemma3:4b and bge-m3 (several GB, Docker Hub)
docker compose --profile llm up ollama-pull # pre-pull before a demo
```

A plain `docker compose up` starts neither and downloads nothing.

`ollama` runs with `OLLAMA_CONTEXT_LENGTH=8192` (override in `.env`). The OpenAI-compatible `/v1` endpoint cannot set the context length per request, and a stage-2 chunk (`analytics-llm-p0`, ADR 0304) is about 3k tokens plus the prompt. Ollama's own default context depends on the version and can be smaller, which truncates the input without an error to the client.

`ollama-pull` pulls every model in `OLLAMA_MODELS` (space-separated, default `gemma3:4b bge-m3`; override in `.env`) and exits non-zero on the first failure. `bge-m3` (about 1.2 GB) serves `/v1/embeddings` for `analytics-embeddings` (ADR 0313); it is local only, with no hosted fallback. Without it analytics still runs with embeddings off. To add it to an existing volume, rerun `docker compose --profile llm up ollama-pull` (already pulled models are only checked). `docker compose exec ollama ollama pull bge-m3` does not work: the serving `ollama` is on `data` only, without internet. `ollama` keeps both models loaded side by side (`OLLAMA_MAX_LOADED_MODELS=2`) for 30 minutes after the last request (`OLLAMA_KEEP_ALIVE=30m`), so stage 2 and the embeddings do not evict each other on every document.

## Development helpers

- **Host ports** (for a module or its tests running on the host): `docker compose -f compose.yaml -f infra/compose.dev-ports.yaml up -d` publishes Postgres, Redis and the object store on `127.0.0.1:15432`, `16379` and `19000` (`IW_DEV_*_PORT`). Loopback only. While the override is loaded these three services also have internet access. Local development only.
- **Parallel worktrees:** set a different `COMPOSE_PROJECT_NAME` (for example `iw-<slug>`) and gateway ports (`IW_HTTPS_PORT`, `IW_HTTP_PORT`) in that worktree's `.env`.
- **Image tags:** the built images (`investwatch/web`, `api`, `analytics`, `scraper`, `renderer`) are tagged with the compose project name (`investwatch/web:iw-<slug>`), so a stack never starts an image another checkout built (issue #63). `IW_VERSION=<version>` replaces that tag with an explicit release tag. The building services set `pull_policy: build`: every `docker compose up` rebuilds from this checkout (cached layers, seconds when nothing changed), and a failed build stops `up` instead of starting the previous image. `docker compose up --no-build` starts the last image of this project on purpose. Old per-project tags pile up; `docker image ls 'investwatch/*'` lists them.
- **Smoke test:** `infra/tests/smoke.sh` checks this whole file against throwaway projects (`SMOKE_LLM=1` also pulls the model). It needs bash, Docker and Node, and runs on Linux, macOS and Git Bash. CI does not run it (`.github/workflows/ci.yml` has no Docker step), so run it locally before changing `infra/`.

## TLS locally

Caddy issues a certificate from its own local CA (`tls internal`), so the browser warns once. To trust it on macOS:

```bash
docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./caddy-root.crt
```

## Secrets

`./scripts/init-env.sh` creates `.env` (mode 600) with a random value for every empty `*_PASSWORD` and `*_SECRET_KEY` in `.env.example`. Run again, it keeps the existing `.env` and exits 0. It never fills `LLM_BASE_URL`, `LLM_MODEL` or `LLM_API_KEY`: set the hosted LLM yourself (ADR 0304). Compose refuses to start without them. `.env` is git-ignored and blocked by the commit hook. Hand-set secrets must be URL-safe; they are embedded in connection URLs.
