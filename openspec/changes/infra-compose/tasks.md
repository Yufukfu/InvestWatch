# Tasks

Before group 1: Damian approves ADR 0306 and the open questions in `design.md` are answered (Kacper for questions 2-3, Adam for question 4). Every check runs through `infra/tests/smoke.sh` against a throwaway project (`-p iw-smoke-$$`, `down -v` on exit).

## 1. Smoke harness and project-scoped networks

- [x] 1.1 Failing test: `infra/tests/smoke.sh` (throwaway env files through a new optional output-path argument of `scripts/init-env.sh`) with a "two stacks at once" check (two projects; the smoke test uses ports 18443/18080 and 18444/18081, so it never clashes with a stack already running on 8443/8080) and a "no cross-stack DNS" check; it fails today because `iw-edge`/`iw-data` are global names
- [x] 1.2 Remove the explicit network `name:` in `infra/compose.yaml` and `web/compose.yaml`; verify `docker compose -p <p> --env-file .env -f web/compose.yaml config` still resolves; both parallel-stack scenarios and the existing gateway check from `infra/CLAUDE.md` "Done" pass
- [x] 1.3 Mutation check (put a fixed `name:` back on one network, the parallel-stack check must fail); mutations: 2 tried, 2 caught (fixed `name:` on `data`, fixed `name:` on `edge`)

## 2. Secrets and env

- [x] 2.1 Failing tests: `.env.example` lists every infrastructure secret empty; a generated `.env` has every secret at 32+ characters and passes `docker compose config`; `init-env` never overwrites and resolves a relative path from the caller; a missing secret is named by `config` (helper `requires_secret`, used for `REDIS_PASSWORD` in group 3 and `MINIO_ROOT_PASSWORD`/`MINIO_SECRET_KEY` in group 4, where the services that need them are added)
- [x] 2.2 Extend root `.env.example` (`REDIS_PASSWORD`, `REDIS_URL` template comment, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ENDPOINT=minio:9000`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET=iw-raw`, `MINIO_SECURE=false`, `OLLAMA_MODEL=gemma3:4b`, `IW_DEV_*_PORT`) and `scripts/init-env.sh` (generate the three new secrets, same length check); the three secret scenarios pass
- [x] 2.3 Mutation check (give one secret a default in compose, its check must fail); mutations: 4 tried, 4 caught (drop `*_SECRET_KEY` from the fill pattern, disable the overwrite guard, default for `POSTGRES_APP_PASSWORD`, relative path resolved from the repo root)

## 3. Redis

- [ ] 3.1 Failing tests: authenticated `PING` returns `PONG` and an unauthenticated one returns `NOAUTH`; `CONFIG GET` shows `appendonly yes` and `maxmemory-policy noeviction`; `iw:settings:thresholds` survives `docker compose restart redis`
- [ ] 3.2 Add `redis` (redis 8-alpine from the ECR mirror, pinned digest) to `infra/compose.yaml` per design decision 2: `iw-data` only, volume `redisdata`, healthcheck, limits, hardening; the three Redis scenarios pass
- [ ] 3.3 Mutation check (drop `--appendonly yes`, then drop `--requirepass`; each must be caught); record `mutations: N tried, N caught`

## 4. Object storage

- [ ] 4.1 Failing tests: `minio-init` exits 0 and `iw-raw` exists; app credentials can put and get `html/<uuid>.html` but cannot create a bucket; anonymous get is denied; a second `up` keeps an existing object
- [ ] 4.2 Read the installed Chainguard `minio` and `minio-client` images (entrypoint, shell, health command) before writing anything; add `minio` and `minio-init` with `infra/minio/init.sh` per design decision 3 and ADR 0306 (pinned digests, volume `miniodata`, `iw-data` only); the four object-storage scenarios pass
- [ ] 4.3 Mutation check (grant the app user `s3:*`, then skip `--ignore-existing`; each must be caught); record `mutations: N tried, N caught`

## 5. Networks, egress and dev ports

- [ ] 5.1 Failing tests: in the default stack only `gateway` publishes ports; a container on `iw-data` only cannot reach a public address; with `infra/compose.dev-ports.yaml` the three data ports listen on `127.0.0.1` only
- [ ] 5.2 Add network `egress` (not internal) to `infra/compose.yaml` and the opt-in `infra/compose.dev-ports.yaml` per design decision 7; the three isolation scenarios pass
- [ ] 5.3 Mutation check (bind a dev port to `0.0.0.0`, then mark `data` non-internal; each must be caught); record `mutations: N tried, N caught`

## 6. Local LLM profile

- [ ] 6.1 Failing tests: without `--profile llm` neither `ollama` nor `ollama-pull` exists and no `ollama_models` volume is created; with the profile `GET /v1/models` lists `gemma3:4b`; with egress blocked `ollama-pull` exits non-zero and the other services stay healthy (the profile test is opt-in, `SMOKE_LLM=1`, because it downloads several GB)
- [ ] 6.2 Add `ollama` and `ollama-pull` behind profile `llm` per design decision 4 (pinned tag, `iw-data` + `egress`, volume `ollama_models`, no host port); the three profile scenarios pass
- [ ] 6.3 Mutation check (remove `profiles: [llm]` from `ollama-pull`, the plain-up check must fail); record `mutations: N tried, N caught`

## 7. Joining contract

- [ ] 7.1 Failing test: a throwaway module service in a test-only compose file under `infra/tests/` with the documented `depends_on` starts only after `postgres`/`redis` are healthy and `minio-init` exited 0, and is not started when `minio-init` is forced to fail
- [ ] 7.2 Write the joining contract in `infra/README.md` (networks per need, `depends_on` conditions, env names, running a module alone with `-p` and `--env-file`, parallel worktree ports, dev-ports override, `--profile llm` and pre-pulling) and the rules in `infra/CLAUDE.md`; both joining scenarios pass
- [ ] 7.3 Mutation check (change `service_completed_successfully` to `service_started`, the failure-blocks-dependants check must fail); record `mutations: N tried, N caught`

## 8. Closing

- [ ] 8.1 Apply the iw-docs-update skill: ADR 0306 final digests, `.docs/decisions/README.md` row, root `README.md` Quick Start (LLM profile), `.docs/integration-plan.md` §1 (include-based `compose.yaml`, object-store note), `.docs/INDEX.md` if a route changes, Damian's own row in `.docs/STATUS.md`; `docs-check` passes; add the iw-ai-log row
- [ ] 8.2 Run the iw-pr-review skill and fix real findings
