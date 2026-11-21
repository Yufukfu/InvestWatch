# Proposal

## Why

`docker compose up` does not run the scraper: the root `compose.yaml` includes infra, web, api and analytics only, and `scraper/` has a runtime image but no compose file. Nothing starts the worker, the scheduler or the seed step, so no scan runs and no document arrives. The brief asks for the whole stack on-premise with one command, and the jury sees the demo through it. `scraper-orchestration` (PR #38, merged) delivered the `worker` and `scheduler` commands and `iw_scraper.seed`; this change deploys them.

## What Changes

- `scraper/compose.yaml` with three services built from the existing `scraper/Dockerfile` (`runtime` target), named `worker`, `scheduler` and `seed`:
  - `worker`: `python -m iw_scraper worker`, healthcheck on `GET /health`, `restart: unless-stopped`.
  - `scheduler`: `python -m iw_scraper scheduler`, one instance, `restart: unless-stopped`, no healthcheck (it serves none).
  - `seed`: one-shot `python -m iw_scraper.seed <cron>`, idempotent, `restart: "no"`, reruns on every `up`. The cron comes from `SCRAPER_SEED_CRON` (default every 6 hours), so the seeded KNF source is scanned on schedule. Without it `schedule_cron` is NULL and the scheduler skips the source.
- Hardening as in `analytics/compose.yaml`, plus the pieces the scraper needs: `tmpfs: [/tmp]` (every fetch spools its body to a temp file), non-root, read-only root filesystem, `cap_drop: [ALL]`, `no-new-privileges`, CPU and memory limits, explicit `environment`, no `env_file`.
- Credentials from the root `.env` through required-variable interpolation: app database role, Redis password, MinIO app user. `worker` and `scheduler` get all three (the shared `runtime()` needs MinIO too); `seed` gets the database URL only. No admin credential anywhere.
- Operator settings passed through as `${VAR:-default}` and added to the root `.env.example`: `PROXY_LIST`, `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`, `DOMAIN_MIN_INTERVAL_SECONDS`, `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES`, `ALLOWED_PORTS`, `COMPOSE_INTERNAL_HOSTS`, `FETCH_EXTRA_HOSTS`, `SCRAPER_SHUTDOWN_DEADLINE`, `SCRAPER_HEALTH_PORT`, `SCRAPER_SEED_CRON`.
- Networks `data` and `egress` only; no host port, not on `edge`.
- One line in the root `compose.yaml` `include:` (Kacper's file: he is told and approves in the PR).
- `.docs/security-audit.md`: a `pip-audit` row for `scraper/requirements.txt` and a scraper container section like the analytics one.
- ADR 0106 records the deployment unit (service split, networks, one scheduler, merge order with `scraper-v3-render`).
- Docs: `scraper/README.md` (Quick Start, hardware note), `scraper/CLAUDE.md`, `.docs/status/scraper.md`, `.docs/integration-plan.md` §2 and its diagram (the doc's `scraper` is `worker` and `scheduler` here), `infra/README.md` and `.docs/INDEX.md` if they name the service, AI log row.
- Out of scope: the renderer, Playwright and the `render` network (`scraper-v3-render`); new sources or seed rows (`scraper-v2-sources`, `scraper-v2-social`); crawling; sample import; fetching a real or stubbed page in the stack check (the production address guard refuses a stub on a compose address, and there is no test switch for it); any scraper code change.
- Owner: Adam's module (`scraper/`); the root `compose.yaml` line belongs to Kacper.
- Contracts: none touched. No REST route, event, database table or object key changes.
- Base: `origin/main`, which already contains PR #38. Rebase or recreate the branch on it before group 1.
- Overlap: `scraper-v3-render` task 3.2 plans to create the same `scraper/compose.yaml` with a `worker`, `stop_grace_period: 45s` and the root include line. This change lands first; that task becomes "add `renderer`, the `render` network and the worker's renderer settings" (design, decision 7).

## Capabilities

### New Capabilities
- `scraper-deployment`: the scraper services in the compose stack, their credentials, networks, hardening, startup order, schedule seed and clean stop.

### Modified Capabilities
<!-- none: shared-infrastructure already defines how a module joins -->

## Impact

- New: `scraper/compose.yaml`, `scraper/tests/stack.sh`, the ADR 0106 file.
- Edited: root `compose.yaml` (one line), root `.env.example`, `.docs/security-audit.md`, `.docs/decisions/README.md`, `.docs/integration-plan.md`, `scraper/README.md`, `scraper/CLAUDE.md`, `.docs/status/scraper.md`.
- No new dependency and no new image. The stack check builds the scraper image (the Dockerfile downloads the pinned tls-client from GitHub), so it needs network.
