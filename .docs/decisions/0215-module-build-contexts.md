# 0215. Each module builds from its own folder; contracts/ is a named build context

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written; accepted by Kacper via PR

## Context

The brief asks for lightweight, separate services: frontend, backend and the AI engine as independent, readable modules, with no heavy monorepo structure. Every module already owns its `compose.yaml` ([ADR 0202](0202-deployment-topology.md)) and no Python package imports another (`investwatch_api`, `iw_scraper` and `investwatch_analytics` have no imports of each other). The build was the exception:

- `web/` builds from `web/` alone, because it keeps a committed contract snapshot ([ADR 0201](0201-web-stack-and-generated-client.md)).
- `analytics/` builds from `../analytics` and puts nothing from `contracts/` in its image.
- `api/` and `scraper/` built from the repository root (`context: ..`, `COPY contracts/...`, `COPY api/...`), only because their images need `contracts/schemas` (the API also needs `contracts/openapi.yaml`) at run time (`CONTRACTS_DIR`). Their whole build context was the repository, so the dependency on `contracts/` was not visible.

## Options considered

1. **Keep the repository root as context.** Works, but the build reads like a monorepo: the context is every folder, and which outside folders an image needs only shows in its `COPY` lines.
2. **A named build context** (`additional_contexts: { contracts: ../contracts }` in compose, `COPY --from=contracts ...` in the Dockerfile; `docker build --build-context contracts=contracts <module>` by hand). Compose supports `additional_contexts` since v2.17 and the README already requires v2.20+. Checked on this machine (Compose v5.7.0, buildx v0.38.1): `docker compose build` builds all six images, the four documented `docker build` commands build, the full stack comes up healthy, and `api/tests/test_compose.py` and the scraper suite pass.
3. **A committed copy of the schemas in each module**, as `web/` does. `web/` has its own reason (it generates TypeScript from the snapshot and checks it with `npm run contracts:check`); for `api/` and `scraper/` it would add two more copies of the same files and a check per copy.
4. **Contracts as a published package** (pip). A shared library with its own versioning and release step: more structure than the brief wants, and `web/` (TypeScript) could not use it.

## Decision

Option 2. `api/` and `scraper/` build from their own folder, and `contracts/` is passed to them by name, the only input from outside a module's folder. The renderer stages of `scraper/Dockerfile` take nothing from `contracts/`. The scraper image now copies only `contracts/schemas`, the one part it reads (`contracts_dir() / "schemas"` in `iw_scraper`), instead of the whole folder. Each build context keeps its own ignore file (`api/Dockerfile.dockerignore`, new `scraper/.dockerignore`); the root `.dockerignore` had no build left and is removed.

## Consequences

- No image builds from the repository root any more; a module's Docker build context is its folder, the same rule for all four modules.
- A plain `docker build <module>` without `--build-context contracts=contracts` fails for `api` and `scraper` with "pull access denied" for `docker.io/library/contracts`; the command is in the first lines of each Dockerfile.
- Paths in compose are `../api`, `../scraper` and `../contracts` (not `.`), so the documented `-f infra/compose.yaml -f api/compose.yaml -f scraper/compose.yaml` chain resolves them too (the reason the include path has, issue #97).
