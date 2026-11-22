---
when: Sun 06:04
who: Kacper
---

## What was done with AI

Asked the agent whether we meet the jury criterion "lightweight modular services: frontend, backend and AI engine as independent, readable modules, no heavy monorepo". It audited `origin/main` (compose graph, cross-module imports, build contexts, which module reads and writes which table and Redis key) and found that `api/` and `scraper/` were the only images built from the repository root. On "maybe contracts should be shared?" it recommended a named build context over a pip package (a shared library is the structure the criterion warns against) or more committed copies. Then it implemented ADR 0215: module-folder contexts, `contracts/` via `additional_contexts`, per-module ignore files, CI and docs.

## Outcome / lesson

Branch `chore/module-build-context`, no OpenSpec change (`IW_SKIP_SPEC=1`, tooling only). Checked: `docker compose build` (6 images), the four documented `docker build` commands, a full stack under its own project name and ports (all 15 services healthy or exited 0, `bootstrap status` ready: 17/17 sources scanned, 223 documents, findings M1 4 / M2 1 / M3 3, visible through the gateway), `api/tests/test_compose.py`, the scraper suite (1673 passed) and the renderer suite (182 passed). One X end-to-end test failed once in the full suite on a 4 GB Docker host with a second stack running and passed 3/3 alone (timing, not the build). Lessons: the teammate's file arrived as `env` (no dot, not git-ignored), so the agent compares before deleting a duplicate secret file; and with `COMPOSE_PROJECT_NAME=investwatch` in `.env`, a test `up` would have taken over another checkout's running stack, so parallel runs need their own project name and ports.
