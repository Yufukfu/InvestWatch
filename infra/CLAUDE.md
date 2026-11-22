# infra

Owners: [`.github/CODEOWNERS`](../.github/CODEOWNERS).

Shared infrastructure: Postgres, Redis, object storage (MinIO), the optional Ollama profile and the Caddy HTTPS gateway. The root `compose.yaml` only `include:`s each module's own `compose.yaml`. What runs where, the roles and the TLS setup are in [`README.md`](README.md); the reasoning is in [ADR 0202](../.docs/decisions/0202-deployment-topology.md) and [ADR 0306](../.docs/decisions/0306-object-storage-image.md). Don't restate them here.

## Rules that are easy to get wrong

- A module adds its own `<module>/compose.yaml` and one line in the root `include:`. Don't put module services in `infra/compose.yaml`.
- Only the gateway publishes host ports (the loopback `compose.dev-ports.yaml` override is opt-in). Network keys are `data` (internal: Postgres, Redis, object store, Ollama), `edge` (routed by the gateway) and `egress` (internet). Never give a network a fixed `name:`; Compose scopes them per project so parallel worktrees don't collide.
- Modules wait on `postgres`/`redis` with `service_healthy` and on `minio-init` with `service_completed_successfully` (joining contract in `README.md`).
- Services use the MinIO app user (`MINIO_ACCESS_KEY`), never the root user. Redis keeps `appendonly yes` and `noeviction` (ADR 0305 thresholds must persist; stream entries must never be evicted).
- `ollama`/`ollama-pull` stay behind `profiles: [llm]`: a plain `up` must download no weights.
- The MinIO image has no curl, wget or grep: health checks and `minio/init.sh` use bash and shell patterns.
- Services connect as `iw_app` (CRUD, no DDL). Migrations run as `iw_admin`: `iw_app` gets grants only on tables `iw_admin` creates.
- `01-app-role.sh` runs only on an empty volume. A role or grant change needs `docker compose down -v` locally, plus a migration for existing databases.
- Secrets come only from `.env` (`scripts/init-env.sh`), with `${VAR:?}` in compose so a missing secret fails loudly. No defaults for passwords.
- HSTS stays off (`IW_HSTS=max-age=0`) on localhost: it ignores ports and would break every local dev server.
- Images come from `public.ecr.aws` mirrors (Docker Hub rate-limits anonymous pulls), pinned by digest. Exceptions: MinIO from `cgr.dev/chainguard` (ADR 0306) and `ollama` from Docker Hub (profile only).

## Done

`docker compose up --build` starts healthy from an empty volume, and `infra/tests/smoke.sh` passes. `https://localhost:8443` and `https://127.0.0.1:8443` serve `web`, `/api` and `/socket.io` reach `api`, and the security headers are present.
