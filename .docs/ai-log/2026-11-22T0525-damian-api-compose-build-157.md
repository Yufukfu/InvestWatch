---
when: Sun 05:25
who: Damian
---

## What was done with AI

A Claude Code session fixed issue #157 (a targeted `up --build --no-deps api` kept the old image). The issue's suggested fix (`build:` on `api` as well) was tested before it was applied, and it failed: with Compose v2.40 two services building one tag aborted `up --build` with "image ... already exists". `build:` on `api` alone also failed: `up api-migrate` without `api`, as `scraper/tests/stack.sh` runs it, tried to pull `investwatch/api` and was denied. The fix gives each service its own tag, with one shared `build:` anchor.

## Outcome / lesson

Verified on a throwaway project `iw-t157` (infra plus api only, removed afterwards): a full `up --build --wait api` was healthy, with one solve and two exports. After an untracked probe file was added, `up -d --build --no-deps api` produced a new image id, recreated `api` and the probe file was in the container. A fresh `up api-migrate` built its own tag. Lesson: test a compose fix suggested in an issue against the containerd image store, and against every command that starts a subset of services, before applying it.
