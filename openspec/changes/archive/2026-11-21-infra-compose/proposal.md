# Proposal

## Why

Every service is blocked on shared infrastructure that does not run yet. `main` already has Postgres and the Caddy gateway through the per-module compose layout of [ADR 0202](../../../../.docs/decisions/0202-deployment-topology.md). It has no Redis (stream `iw:documents`, pub/sub `iw:events`, key `iw:settings:thresholds`), no object storage for bucket `iw-raw`, and no local LLM fallback. Integration #1 (Sat 17:00) needs all three of the first two. The milestone "compose infra up" (`.docs/integration-plan.md` §8) is still open.

## What Changes

- Add `redis` to `infra/compose.yaml`: Redis 8 with AOF persistence (ADR 0305 needs thresholds to survive a restart), `noeviction` so stream entries are never dropped, a required password, a healthcheck and a named volume. It is reachable only on the internal network `data`.
- Add object storage with bucket `iw-raw` to `infra/compose.yaml`. The service is named `minio`, and a one-shot `minio-init` creates the private bucket and a least-privilege app user limited to it. The official MinIO community images can no longer be pulled, so the image source is decided in a new ADR 0306 written by this change (see `design.md`).
- Add an optional `ollama` service serving `gemma3:4b` behind the compose profile `llm`, plus a one-shot `ollama-pull`. A plain `docker compose up` starts neither and downloads no weights (ADR 0304).
- Add a non-internal network `egress` (Docker name `<project>_egress`) for services that need outbound internet: the scraper, analytics (hosted LLM) and the `ollama-pull` step. `data` stays internal, and only the gateway publishes host ports (ADR 0202).
- Make network names project-scoped, so two stacks with different `COMPOSE_PROJECT_NAME` and gateway ports (parallel worktrees, `iw-implement` step 3) never share a network or a DNS name. This is a small edit to `infra/compose.yaml` and `web/compose.yaml`, owned by Kacper.
- Extend the root `.env.example` and `scripts/init-env.sh` with the Redis and object-storage secrets and the client variables `REDIS_URL` and `MINIO_*` (`.docs/integration-plan.md` §7). Compose refuses to start without the secrets (`${VAR:?}`), as it already does for Postgres.
- An opt-in override `infra/compose.dev-ports.yaml` publishes Postgres, Redis and the object store on `127.0.0.1` only. It is for running a module or its tests on the host before that module has a container.
- Record the joining contract for `scraper`, `analytics` and `api` in `infra/README.md`: networks, `depends_on` conditions and env names. Each module adds its own `compose.yaml` and Dockerfile in its own change, plus one line in the root `include:`.
- Out of scope: the `scraper`, `analytics`, `api` and `web` containers and their Dockerfiles; the Alembic migration step (ADR 0303, `api` change); creating the stream consumer group (done by analytics with `XGROUP CREATE ... MKSTREAM`); writing default thresholds (done by `api`, ADR 0305); TLS between services; backups.
- Owner: Damian (module C, compose infra per `.docs/integration-plan.md`). The files under `infra/`, `web/compose.yaml` and `scripts/init-env.sh` are owned by Kacper ([ADR 0202](../../../../.docs/decisions/0202-deployment-topology.md), `infra/CLAUDE.md`), so Kacper reviews the PR.
- Contracts: none. No JSON Schema, REST route or event shape changes. The change provides the Redis names and the bucket that integration points 2, 3 and 5 (`.docs/integration-plan.md` §2) and ADR 0305 already define.

## Capabilities

### New Capabilities
- `shared-infrastructure`: the Redis, object storage and optional local LLM services in compose, their secrets and networks, isolation between parallel stacks, and the contract a module follows to join the stack.

### Modified Capabilities

## Impact

- Files: `infra/compose.yaml`, new `infra/compose.dev-ports.yaml`, new `infra/minio/init.sh`, `infra/tests/` (`smoke.sh` and test-only compose files), `web/compose.yaml` (network names only), root `.env.example`, `scripts/init-env.sh`.
- Images (added): `public.ecr.aws/docker/library/redis:8-alpine`, the object-storage and client images from ADR 0306 (pinned by digest), and `docker.io/ollama/ollama` (pinned tag, profile `llm` only).
- Docs: new ADR `.docs/decisions/0306-object-storage-image.md` and its row in the decisions README; `infra/README.md`, `infra/CLAUDE.md`, root `README.md` Quick Start (LLM profile), `.docs/integration-plan.md` §1 (`docker-compose.yml` becomes the include-based `compose.yaml`, and the object-storage note). `.docs/STATUS.md` is updated by Damian.
- Unblocks: `scraper-v1` groups 5-6 (real Postgres, MinIO and Redis), the analytics worker and the `api` service.
