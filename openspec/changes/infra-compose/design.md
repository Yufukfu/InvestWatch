# Design

## Context

`main` already runs the per-module layout of [ADR 0202](../../../.docs/decisions/0202-deployment-topology.md). The root `compose.yaml` only `include:`s `infra/compose.yaml` (Postgres 17 on the internal network `iw-data`, the Caddy gateway on `iw-edge`, the only published ports) and `web/compose.yaml`. Secrets come from `.env` via `scripts/init-env.sh`, with `${VAR:?}` guards. Images come from `public.ecr.aws` mirrors because Docker Hub rate-limits anonymous pulls. The older docs (`.docs/integration-plan.md` §1, `scraper/CLAUDE.md`, `scraper-v1`) still say `docker-compose.yml`. This change keeps 0202's layout and does not bring back a single file.

Missing pieces that consumers already depend on:

- Redis: stream `iw:documents` (scraper → analytics), pub/sub `iw:events` (analytics → api), key `iw:settings:thresholds`, which must persist (ADR 0305 asks for AOF), and the analytics LLM response cache (`.docs/analytics-plan.md` §7).
- Object storage: bucket `iw-raw` with `html/`, `shot/` and `media/` keys (`.docs/integration-plan.md` §2), read by `api` for screenshots.
- Local LLM fallback: `ollama` with `gemma3:4b` behind a profile (ADR 0304).

Evidence gathered on 2026-11-21 with `docker manifest inspect` (metadata only, nothing pulled). These images can be pulled: `public.ecr.aws/docker/library/redis:8-alpine`, `cgr.dev/chainguard/minio:latest`, `cgr.dev/chainguard/minio-client:latest` and `docker.io/ollama/ollama:latest`. These cannot: `docker.io/minio/minio:latest` (access denied), `quay.io/minio/minio:latest` and `:RELEASE.2025-09-07T16-13-09Z` (no manifest), `public.ecr.aws/docker/library/valkey:8-alpine` and `.../ollama` (no manifest). `docker.io/chrislusf/seaweedfs` answered with the anonymous rate limit (HTTP 429). Tooling: Docker 28.5.1 and Compose v2.40.0.

Stakeholders: Damian (owner of the change and of the `api` and `analytics` compose files), Kacper (owner of `infra/`, `web/compose.yaml` and `scripts/`, so reviewer of this PR), and Adam (consumer: scraper needs Postgres, Redis, MinIO and internet).

## Goals / Non-Goals

**Goals:**
- `./scripts/init-env.sh && docker compose up` brings up postgres, redis, minio (with `iw-raw`), gateway and web, all healthy, and downloads no LLM weights.
- `docker compose --profile llm up` adds local Gemma at `http://ollama:11434/v1`.
- Two worktrees can run full stacks side by side.
- A module joins with its own compose file and one `include:` line, using a documented contract.

**Non-Goals:**
- Module containers and Dockerfiles (scraper, analytics, api), the `migrate` step (ADR 0303), consumer groups and default thresholds (created by their owners at runtime).
- High availability, backups, TLS between services, a MinIO console exposed on the host.

## Decisions

1. **Shared services go into `infra/compose.yaml`, not a new file.** ADR 0202 and `infra/CLAUDE.md` say shared infrastructure lives there and module services do not. Redis and the object store are used by three modules, so they are shared. Ollama is consumed only by analytics, but it is an optional backend, not module code. Keeping it in `infra/` under a profile means analytics' compose file stays independent of whether the fallback is on. Alternative: `analytics/compose.yaml` owns `ollama`. That couples the fallback to the analytics change, which a sibling session is writing in parallel. (Open question 2.)

2. **Redis 8 from the ECR mirror, configured on the command line.** `sh -c` runs `umask 0077` and then `exec redis-server - --appendonly yes --appendfsync everysec --maxmemory 128mb --maxmemory-policy noeviction`, with `requirepass` fed in through a heredoc. It is a heredoc, not a pipe, so `exec` replaces PID 1 and Redis gets SIGTERM for a clean shutdown. The password comes over stdin (`-` reads config from it), so it is never in a tracked file or in the process arguments, even for the moment before Redis rewrites its process title. `umask 0077` keeps the AOF files private, since a `sh` command bypasses the image entrypoint that would set it. `maxmemory 128mb` is half the 256M container limit, leaving room for the copy-on-write fork of an AOF rewrite. At the cap, producers get OOM errors on writes instead of losing stream entries. The container runs as user `redis` with a read-only root filesystem. Healthcheck: `redis-cli` with `REDISCLI_AUTH` returning `PONG`. Redis 8 is offered under AGPLv3 (OSI-approved) as one of its three licences. Redis 7.4 is source-available only, and Valkey (BSD) is not on the ECR mirror at the tag tried. Client URL: `REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0`. Memory limit 256M, `no-new-privileges`, `cap_drop: [ALL]`.

3. **Object store: MinIO server built from source by Chainguard, pinned by digest; service name stays `minio`.** Recorded as [ADR 0306](../../../.docs/decisions/0306-object-storage-image.md). Keeping the name `minio` and the `MINIO_*` variables leaves the contracts, mocks (`contracts/mocks/health.json`), `scraper-v1` and the docs unchanged. Clients speak S3, so a later swap to another S3 server changes only the image and init script.
   - `minio` runs `server /data`, with root credentials from `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`, a named volume `miniodata`, and a healthcheck on `/minio/health/live`. The image has `bash` but no curl, wget or grep, so the healthcheck sends a plain HTTP/1.1 request over `/dev/tcp` with no credentials. The web console is off (`MINIO_BROWSER=off`).
   - `minio-init` (one-shot, `restart: "no"`) uses the same pinned `minio` image, which ships `sh` and `mc`. The separate `minio-client` image has no shell, so it cannot run a script. It runs `infra/minio/init.sh`, which passes the root credentials through `MC_HOST_iw` (environment, not argv), makes `iw-raw` if missing (`mb --ignore-existing`), sets anonymous access to `none`, creates the policy `iw-bucket-rw` (`s3:GetObject`, `PutObject`, `DeleteObject` on `iw-raw/*`, `ListBucket` and `GetBucketLocation` on `iw-raw`), and creates or updates user `MINIO_ACCESS_KEY` attached to that policy. Services never get root credentials, the same split as `iw_admin` and `iw_app` in Postgres.

4. **Ollama behind profile `llm`, on `iw-data` and `iw-egress`.** `ollama` (pinned tag of `docker.io/ollama/ollama`, the only registry that served it) keeps its models in volume `ollama_models` and has a healthcheck `ollama list`. `ollama-pull` (same image, `OLLAMA_HOST=ollama:11434`, `depends_on: ollama: service_healthy`) runs `ollama pull ${OLLAMA_MODEL:-gemma3:4b}` and exits. Pulling needs internet, so `ollama` joins `iw-egress`. Analytics reaches it on `iw-data`, with `LLM_BASE_URL=http://ollama:11434/v1`, `LLM_MODEL=gemma3:4b` and any non-empty `LLM_API_KEY`. The one Docker Hub image is pulled only with the profile, so Docker Hub rate limits never affect a plain `up`. Memory limit 6G.

5. **A third network, `iw-egress`, for outbound internet.** `iw-data` stays internal (ADR 0202, verified there), and `iw-edge` stays the gateway's routing network. Without a separate egress network, the scraper and analytics would join `iw-edge` just to reach the internet, which mixes routing with egress. Alternative: services needing internet join `iw-edge`. That is one network fewer, but every routed service then also has egress, and the rule "which services can reach the internet" is no longer visible from the network list.

6. **Project-scoped network names.** The current `name: iw-edge` and `name: iw-data` are global. A second worktree's stack would attach to the same networks, and `redis` or `postgres` would resolve to two containers. Drop the explicit `name:` and let Compose prefix it with the project (`<project>_data`). With `include:` all modules are one project, so they still share these networks. A module run on its own (`docker compose -f web/compose.yaml up`) then needs `-p <project>` and `--env-file .env`. `infra/README.md` documents that. Alternative: `name: ${COMPOSE_PROJECT_NAME}-data`. It works only if the variable is set for interpolation in every way of invoking compose (`-p` on the command line versus `.env`), which is more to get wrong than letting Compose prefix the name. Volumes are already project-scoped. Parallel worktrees also set `IW_HTTPS_PORT` and `IW_HTTP_PORT` (already variables), and `iw-implement` suggests `COMPOSE_PROJECT_NAME=iw-<slug>`.

7. **Dev ports through an opt-in override, not a profile.** Compose cannot add or remove `ports:` by profile, and a container only on an `internal` network cannot publish ports. `infra/compose.dev-ports.yaml` therefore attaches `postgres`, `redis` and `minio` also to a non-internal `devhost` network, and binds `127.0.0.1:${IW_DEV_PG_PORT:-15432}`, `${IW_DEV_REDIS_PORT:-16379}` and `${IW_DEV_MINIO_PORT:-19000}`. These are not the standard ports, so a native Postgres or Redis keeps running, and they are variables, so parallel stacks can choose different ones. 55432/56379 were dropped because other sessions' test containers already bind them on this machine. A plain `docker compose up` never loads it. (Open question 3.)

8. **Testing is a shell smoke test, `infra/tests/smoke.sh`.** It runs against a throwaway project (`-p iw-smoke-$$`, its own ports, `down -v` on exit) and checks every scenario in the spec using `docker compose exec` / `run` probes. It needs no host ports and no languages beyond `sh` and Docker. Each task group adds its checks before the compose change (failing first).

## Risks / Trade-offs

- [Chainguard free images publish only `latest`, and an old digest may disappear] → Pin by digest, record the digest in ADR 0306, and treat a missing digest as a one-line bump. The ADR names SeaweedFS as the fallback.
- [Upstream MinIO community edition is archived, so security fixes come only through rebuilds] → It is reachable only on `iw-data` with no host port, credentials are bucket-scoped, and ADR 0306 says to revisit after the hackathon.
- [Redis AGPLv3 / MinIO AGPLv3 licences] → We run them unmodified as separate services, which the jury's open-source requirement accepts. Named in the ADR and later in the hand-in README.
- [Ollama pull is several GB and Docker Hub may rate-limit] → Profile only. Pre-pull before the demo (`docker compose --profile llm up ollama-pull`). The rules-only fallback in analytics covers an unreachable LLM.
- [Removing fixed network names changes how a module is run alone] → Documented command in `infra/README.md`. `web/compose.yaml` is edited in the same PR with Kacper reviewing.
- [`noeviction` means writes fail when memory is full instead of dropping data] → That is the intended failure for streams. The 256M limit is far above a hackathon's volume, and a full instance shows up as write errors in the producer logs.
- [The Redis password travels in `REDIS_URL` inside container env] → The same exposure as `POSTGRES_APP_PASSWORD` today. It is never logged (root `CLAUDE.md` hard rule).

## Migration Plan

Additive. Existing local stacks need `scripts/init-env.sh`, which refuses to overwrite `.env`, so teammates add the new variables from `.env.example` by hand or regenerate `.env` and then run `docker compose down -v` (it wipes only local data). Network renaming needs `docker compose down` once, because old `iw-edge`/`iw-data` networks are left behind. Rollback: revert the PR. No data is migrated.

## Open Questions

1. ADR 0306 picks Chainguard's MinIO build. Does Damian accept it, or prefer SeaweedFS (Apache-2.0, but a different service, a rename across docs, and Docker Hub only)?
2. Kacper owns `infra/`, `web/compose.yaml` and `scripts/init-env.sh` (ADR 0202). Is he OK with Damian's change editing them, with `ollama` living in `infra/compose.yaml` under a profile rather than in `analytics/compose.yaml`?
3. Kacper and Adam: is the opt-in `compose.dev-ports.yaml` (loopback only) acceptable, or should host-side development run only inside containers?
4. Adam: does `scraper` need anything else from shared infra, for example a Redis database number for the job queue if ADR 0102 picks `arq` or `rq`? Proposed default: the same Redis, db `0`, key prefix `iw:scraper:`.
