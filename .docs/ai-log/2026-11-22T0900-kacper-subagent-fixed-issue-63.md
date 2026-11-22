---
when: Sun ~morning
who: Kacper
---

## What was done with AI

A Claude Code subagent fixed issue #63 (a stack silently ran another checkout's stale `investwatch/web:dev` after a failed `--build`). It first checked on Compose v5.7 in a scratch project that `${COMPOSE_PROJECT_NAME}` interpolates for `-p`, `.env` and the directory default, and that `pull_policy: build` makes a plain `up` fail on a broken build instead of starting the old image.

## Outcome / lesson

Branch `infra/per-project-image-tags`: per-project tags plus `pull_policy: build` on the four building services, `IW_VERSION` still the release tag; `docker compose config --images` checked for the root file and each module's own command. Another lesson: a real web build failed on `main` from the open vitest timeout (#60), the same failure this fix now makes visible instead of hiding.
