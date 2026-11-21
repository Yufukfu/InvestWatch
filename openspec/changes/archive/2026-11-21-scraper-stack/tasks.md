# Tasks

Before group 1: the branch is on `origin/main` (it has PR #38; the branch was cut from the pre-squash #38 head, so recreate it from `origin/main` and keep this change directory). Every check runs through `scraper/tests/stack.sh` against a throwaway project (`-p iw-stack-$$`, `down -v` on exit, no host ports); it builds the scraper image and needs network.

## 1. Stack check and compose file

- [x] 1.1 Write `scraper/tests/stack.sh` with every scenario of `scraper-deployment` red before any compose file exists: services, gates (`docker compose config --format json`), restart policies, single scheduler, seed override that fails, rerun and one KNF row, non-null cron and invalid cron, structural no-default secrets, no admin string, seed holds less, networks and no ports, health from a throwaway container on `data`, hardening via `docker inspect`, read-only write refused, grace arithmetic, idle stop; it fails because `scraper/compose.yaml` does not exist
- [x] 1.2 Add `scraper/compose.yaml` per design decisions 1 to 7 (including the pass-through variables in the root `.env.example`) and make `seed` reject an invalid cron (`cron_from`, unit test written red first); the scenarios pass (10 run, 12 config)
- [x] 1.3 Mutation check (add a host port; put `worker` on `edge`; drop `read_only`; drop `cap_drop`; drop `tmpfs`; add `MINIO_ROOT_PASSWORD` to `worker`; remove the `seed` gate; remove `:?` from `DATABASE_URL`; `replicas: 2` on `scheduler`; `stop_grace_period: 35s`; drop the seed cron argument; each must be caught) and write `mutations: N tried, N caught` on this line: mutations: 13 tried, 13 caught (the 11 above plus `scheduler` on `egress` and a plain `${POSTGRES_APP_PASSWORD}` in `seed`, added after review; each caught by its own check, `stack.sh config`)

## 2. Join the root stack

- [x] 2.1 Failing test: `docker compose config` at the repo root lists `worker`, `scheduler` and `seed`; it fails because the root file does not include the scraper
- [x] 2.2 Add `scraper/compose.yaml` to the root `include:`; the root file passes "Whole stack starts" (no fetch; `STACK_ROOT=1 scraper/tests/stack.sh run` runs every scenario through it, the default `root` group checks `config --services` only); tell Kacper about the line in the PR body
- [x] 2.3 Mutation check (remove the include line; rename a service; each must be caught) and write `mutations: N tried, N caught` on this line: mutations: 2 tried, 2 caught (`stack.sh root`)

## 3. Audit and docs

- [x] 3.1 Run `pip-audit -r scraper/requirements.txt -r scraper/requirements-dev.txt`; fix or record any finding; add the dated row (format `| date | scraper (scraper-stack) | command (versions) | result |`) and a scraper container section (credentials, networks, `/health`, untrusted input, container) to `.docs/security-audit.md`; check each claim against `scraper/compose.yaml`
- [x] 3.2 Write ADR 0106 (decisions 1, 3, 7, 8 with the compose files read and the stack check output as evidence) and its row in `.docs/decisions/README.md`
- [x] 3.3 Mutation check: n/a, documentation only (audit claims are checked against the compose file in 3.1)

## 4. Closing tasks

- [x] 4.1 Apply the `iw-docs-update` skill (`scraper/README.md` Quick Start and hardware note, `scraper/CLAUDE.md`, `.docs/status/scraper.md`, `.docs/integration-plan.md` §2 and diagram, grep `infra/README.md` and `.docs/INDEX.md` for the service name), run `docs-check` clean, and add the `iw-ai-log` row
- [x] 4.2 Run the `iw-pr-review` skill and fix real findings
