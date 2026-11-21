# 0106. Scraper deployment unit

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the human via the PR that merges `scraper-stack`

## Context

`scraper-orchestration` (PR #38) delivered `python -m iw_scraper worker|scheduler` and `iw_scraper.seed`, but the root `compose.yaml` included only infra, web, api and analytics, so `docker compose up` ran no scan. `scraper-stack` (`openspec/changes/archive/2026-11-21-scraper-stack/`) deploys them. Facts read in code: `runtime()` in `app.py` is shared by both commands and opens Postgres, Redis and MinIO before starting; `scheduler.py` makes no HTTP call; `worker.py` defines `CLOSE_TIMEOUT = 10.0` and the shutdown deadline is `SCRAPER_SHUTDOWN_DEADLINE` (default 30 s); `infra/compose.yaml` declares `data` as `internal: true` and `egress` as the route out. `scraper-v3-render` (branch `scraper/scraper-v3-render`, task 3.2) also plans to create `scraper/compose.yaml`, with `stop_grace_period: 45s`.

## Options considered

1. **Service split.** (a) one container running worker and scheduler as two processes; (b) one image, three compose services `worker`, `scheduler`, one-shot `seed`; (c) a separate image per role. (a) needs a supervisor and mixes SIGTERM handling and health of two roles. (c) duplicates the Dockerfile's `runtime` target, which already carries the code for every command.
2. **Networks.** (a) `data` and `egress` for every service (what `analytics` and the first draft of the spec assumed); (b) `egress` only on the service that fetches. Only `worker` fetches (`scheduler.py` has no HTTP call; `seed` touches Postgres only).
3. **Stop grace.** The worker needs the 30 s deadline plus up to 10 s to requeue; the 45 s planned by `scraper-v3-render` leaves 5 s of margin and breaks if an operator raises the deadline.
4. **Who creates `scraper/compose.yaml`.** `scraper-stack` first, or `scraper-v3-render` first. Either way the other adds only its own parts.

## Decision

1. Three services from one image (`investwatch/scraper`, `runtime` target): `worker` (scaled with `--scale`), exactly one `scheduler`, and a one-shot `seed` rerun on every `up` that passes `SCRAPER_SEED_CRON` (default `0 */6 * * *`) so the seeded source is scheduled. `seed` rejects an invalid cron before connecting.
2. `worker` on `data` and `egress`; `scheduler` and `seed` on `data` alone. No host port, never on `edge`.
3. `stop_grace_period: 60s` for `worker` and `scheduler`, kept at deadline plus 20 s; `stack.sh` reads both numbers from `docker compose config` so a raised deadline fails the check.
4. `scraper-stack` creates `scraper/compose.yaml` and the root include line (Kacper is told in the PR). `scraper-v3-render` adds only `renderer`, the `render` network, the worker's renderer settings and no include line, and keeps 60 s; whichever branch merges second rebases, and the conflict is limited to `scraper/compose.yaml`.

## Evidence

- `scraper/tests/stack.sh` on the branch: `config` 12 passed, `root` 1 passed, `run` 10 passed (also through the root file with `STACK_ROOT=1`): seed exits 0, `worker` healthy, `scheduler` running with `RestartCount` 0, no published port, health answers from a container on `data` and not on the host, containers non-root and read-only, a write under `/app` refused, a second start keeps one KNF row, `docker compose stop worker` exits 0 well under 20 s.
- Mutation check: 13 of 13 compose mutations and 2 of 2 root mutations are caught by their own check.
- The stack check proves wiring, not a fetch: the production address guard refuses a stub on a compose address and has no test switch, so a real fetch stays with the opt-in live smoke test of `scraper-orchestration`.

## Consequences

- One demo-ready `docker compose up` runs scheduled and requested scans; offline machines show recorded `job_errors` while health stays green.
- Limits (`worker` 1 CPU / 768 MB, `scheduler` 0.5 / 256 MB, `seed` 0.5 / 128 MB) and the 128 MB `/tmp` tmpfs are first guesses to adjust after the first run on the demo machine.
- `scraper-v3-render` task 3.2 must be amended before it is reached.
