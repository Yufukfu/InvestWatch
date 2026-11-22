# Proposal

## Why

Issue #97. `scraper/compose.yaml` includes `compose.renderer.yaml` by a bare relative path. Compose resolves an include of a merged `-f` chain against the project directory, the first `-f` file's directory, so the documented chain `docker compose -f infra/compose.yaml -f api/compose.yaml -f scraper/compose.yaml` fails with `open .../infra/compose.renderer.yaml: no such file or directory` (Docker Compose v5.2.0, reproduced on `origin/main`). The root `compose.yaml` works because nested includes resolve against the including file's directory. `stack.sh` hides the failure by wrapping the modules in an include file.

## What Changes

- `scraper/compose.yaml` includes `../scraper/compose.renderer.yaml`: the same `..` form that `build.context` uses, and valid whether the project directory is the repo root, `infra/`, `api/` or `scraper/`.
- ADDED requirement "Module files merge in any order" to `scraper-deployment`, with a scenario that merges the documented `-f` chain and one that reads the same model from the root file.
- `scraper/tests/stack.sh` root group: a scenario that merges the module files with several `-f` (the documented chain) and checks `renderer` is in the model.

## Out of scope

- The other modules' compose files and PRs #90 and #95 (they change image tags and header comments, not the include line).
- Any contract, REST route or event: this change touches none. Module owner: `scraper/` (Adam).

## Impact

- `scraper/compose.yaml` (one line), `scraper/tests/stack.sh`, `openspec/specs/scraper-deployment/spec.md` (by archive).
- Expected textual conflict: PR #90 edits `scraper/compose.yaml` on the lines right after the include (the image tag), so a one-line resolution may be needed in whichever PR merges second.
