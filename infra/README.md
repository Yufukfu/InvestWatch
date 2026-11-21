# infra

Shared infrastructure, owned by Kacper (repository layout). Each module has its own `compose.yaml`; the root `compose.yaml` only includes them, so a module is deployed, scaled or replaced without touching the others. Reasoning: [ADR 0202](../.docs/decisions/0202-deployment-topology.md) (topology), [ADR 0306](../.docs/decisions/0306-object-storage-image.md) (object storage and Redis images), [ADR 0304](../.docs/decisions/0304-llm-serving.md) (LLM fallback).

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

## Database access

- `iw_admin` (from `POSTGRES_ADMIN_*`): migrations and ops only.
- `iw_app` (from `POSTGRES_APP_*`): what services use. CRUD on tables in `public`, no DDL, no superuser.
- Connection for services on `data`: `postgresql://iw_app:<password>@postgres:5432/investwatch`.
- Schema comes from migrations (Alembic in `api`, owner Damian), never by hand. Run migrations as `iw_admin`: `iw_app` gets CRUD automatically only on tables created by `iw_admin`. The init script runs only on an empty volume; to reset: `docker compose down -v`.

## Object storage access

- Root user (`MINIO_ROOT_*`): `minio-init` only.
- App user (`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`): read, write, delete and list objects in `iw-raw`; no other bucket, no admin. Anonymous access is off.
- Keys: `html/{document_id}.html`, `shot/{document_id}/{viewport}.png`, `media/{document_id}/{n}.{ext}` ([integration-plan.md](../.docs/integration-plan.md) §2).

## Local LLM (optional)

```bash
docker compose --profile llm up -d          # adds ollama and pulls gemma3:4b (several GB, Docker Hub)
docker compose --profile llm up ollama-pull # pre-pull before a demo
```

A plain `docker compose up` starts neither and downloads nothing.

## Development helpers

- **Host ports** (for a module or its tests running on the host): `docker compose -f compose.yaml -f infra/compose.dev-ports.yaml up -d` publishes Postgres, Redis and the object store on `127.0.0.1:15432`, `16379` and `19000` (`IW_DEV_*_PORT`). Loopback only. While the override is loaded these three services also have internet access. Local development only.
- **Parallel worktrees:** set a different `COMPOSE_PROJECT_NAME` (for example `iw-<slug>`) and gateway ports (`IW_HTTPS_PORT`, `IW_HTTP_PORT`) in that worktree's `.env`.
- **Smoke test:** `infra/tests/smoke.sh` checks this whole file against throwaway projects (`SMOKE_LLM=1` also pulls the model). It needs bash, Docker and Node, and runs on Linux, macOS and Git Bash. CI does not run it (`.github/workflows/ci.yml` has no Docker step), so run it locally before changing `infra/`.

## TLS locally

Caddy issues a certificate from its own local CA (`tls internal`), so the browser warns once. To trust it on macOS:

```bash
docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./caddy-root.crt
```

## Secrets

`./scripts/init-env.sh` creates `.env` (mode 600) with a random value for every empty `*_PASSWORD` and `*_SECRET_KEY` in `.env.example`. Run again, it keeps the existing `.env` and exits 0. It never fills `LLM_BASE_URL`, `LLM_MODEL` or `LLM_API_KEY`: set the hosted LLM yourself (ADR 0304). Compose refuses to start without them. `.env` is git-ignored and blocked by the commit hook. Hand-set secrets must be URL-safe; they are embedded in connection URLs.
