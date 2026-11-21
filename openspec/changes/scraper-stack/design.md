# Design

## Context

- Base is `origin/main`, which has PR #38: `python -m iw_scraper worker|scheduler`, `iw_scraper.seed [CRON]`, `GET /health` on `SCRAPER_HEALTH_PORT` (default 8080, bound to `0.0.0.0`). `scraper/Dockerfile` has the `runtime` target (`USER iw`, `curl` installed in the base stage). There is no deployable `scraper/compose.yaml`, and the root `compose.yaml` does not include the scraper.
- `runtime()` in `app.py` is shared by both commands: it requires `DATABASE_URL`, `REDIS_URL` and `MINIO_ENDPOINT`/`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` and calls `check_bucket()` before starting. `worker`'s `/health` returns 503 when Postgres, Redis or MinIO fails, so "healthy" proves all three.
- `seed.py` needs only `DATABASE_URL`; with no cron argument `schedule_cron` stays NULL and `scheduler.tick()` skips the source.
- `fetch.py` spools each body to `tempfile.mkstemp`, so `/tmp` must be writable. `worker` stops by letting running jobs finish for `SCRAPER_SHUTDOWN_DEADLINE` (30 s), then requeueing for up to `CLOSE_TIMEOUT` (10 s).
- The address guard refuses private addresses and bare host names, so a scraped URL cannot reach Redis or MinIO on `data`.
- Patterns: `infra/compose.yaml` (networks, `egress`), `api/compose.yaml` (`api-migrate`, python health probe), `analytics/compose.yaml` (hardening). `.docs/security-audit.md` has a container section for analytics on `origin/main`.

## Goals / Non-Goals

**Goals:** one `docker compose up` runs scheduled and requested scans; least credentials; a script proves it.

**Non-Goals:** the renderer; scaling tests beyond `--scale worker=N` (the code supports it); live fetches in the stack check.

## Decisions

1. **Three services, one image** (`investwatch/scraper:${IW_VERSION:-dev}`), build context `..`, `dockerfile: scraper/Dockerfile`, `target: runtime`. One scheduler per stack (a second only wastes ticks), workers scale. One process per role keeps SIGTERM and health per role.
2. **`seed` is a compose one-shot**, gated by `api-migrate` and healthy Postgres, `restart: "no"`, rerun on every `up` (idempotent by URL). It passes `${SCRAPER_SEED_CRON:-0 */6 * * *}` as the argument. When `scraper-v2-sources` extends `seed` the argument keeps meaning "the cron for rows seeded here"; that change decides it for its own rows.
3. **Networks `data` and `egress`.** `data` is internal, so the internet needs `egress`. No `edge`, no host port.
4. **Environment.** `worker` and `scheduler`: `DATABASE_URL` (app role), `REDIS_URL`, `MINIO_*` (app user), `LOG_LEVEL`, and the pass-through settings from the proposal as `${VAR:-default}` using the defaults of `scraper/.env.example`. `seed`: `DATABASE_URL` only. `PROXY_LIST` may hold credentials and is passed from the root `.env`; `scripts/init-env.sh` leaves it empty. `depends_on` as in the spec.
5. **Health.** `worker`: `["CMD","python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:${SCRAPER_HEALTH_PORT:-8080}/health', timeout=3)"]` as `api` does, `interval 10s`, `timeout 5s`, `retries 5`, `start_period 20s`. `scheduler` has none; the check asserts `State.Running` and `RestartCount == 0` after a settle time. The "from a container on `data`" scenario uses a throwaway container on `<project>_data` (an image infra's test already pulls).
6. **Resources and tmpfs.** `tmpfs: [/tmp]`, sized `size=128m`; tmpfs counts toward the memory limit, and the worst case is `FETCH_MAX_BYTES` (5 MiB) times `SCRAPER_MAX_JOBS` (10). Initial limits, assumptions to adjust after the first run: `worker` 1 CPU and 768 MB, `scheduler` 0.5 CPU and 256 MB, `seed` 0.5 CPU and 128 MB.
7. **Stop grace 60 s** = 30 (`SCRAPER_SHUTDOWN_DEADLINE`) + 10 (`CLOSE_TIMEOUT`) + margin. The spec's invariant is `grace >= deadline + 20`; the stack check reads both from `docker compose config` so an operator who raises the deadline sees it fail. `scraper-v3-render` task 3.2 names 45 s; after this change it keeps this value.
8. **Merge order with `scraper-v3-render`.** This change creates `scraper/compose.yaml` and the root include line. `scraper-v3-render` then adds `renderer`, the internal `render` network, `worker` on it and its settings, and does not add its own include line. Whichever branch is second rebases on the first; the conflict is limited to `scraper/compose.yaml`. The owner of both is the same person, so amend task 3.2 of `scraper-v3-render` before it is reached.
9. **No fetch in the stack check.** The production guard refuses bare names and every non-global address and allows only ports 80 and 443; the in-process tests relax it with a loopback shim that has no environment switch. The check therefore proves wiring (`seed`, health, scheduler up, networks, hardening, stop), not a fetch. The opt-in live smoke test from `scraper-orchestration` covers a real fetch and stays opt-in.
10. **Check as a script.** `scraper/tests/stack.sh` reuses the `new_env` helper of `infra/tests/smoke.sh` (env file from `.env.example`, secrets filled, project name and ports set), runs `-p iw-stack-$$`, `down -v` on exit, no host ports. Secrets are asserted structurally (the three variable lines use `${VAR:?`), because infra and api files fail on the same unset variables first.
11. **ADR 0106** records decisions 1, 3, 7 and 8. Re-check that the number is free on all branches when writing it (0105 is claimed three times).

## Risks / Trade-offs

- Read-only filesystem: `/tmp` is the one known write path. If the first run shows another (`noble-tls` is baked into the image, so none expected), that path gets its own tmpfs, never a writable root.
- `seed` rerunning on every `up` costs one query; intended.
- Offline machine: the worker starts, every job fails with a recorded `job_errors` row, health stays green. Acceptable and visible.
- Limits are guesses. A job killed by the memory limit shows as a restart; adjust numbers in `scraper/compose.yaml` and the audit section together.

## Open Questions

None blocking. Whether the stack should also pass the remaining `SCRAPER_*` tuning variables is left out on purpose: defaults are tested, and compose can add them when a demo needs one.
