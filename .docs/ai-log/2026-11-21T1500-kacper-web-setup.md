---
when: Sat 15:00
who: Kacper
---

## What was done with AI

Claude Code set up the web foundation (OpenSpec change `web-setup`): Vite/React app, RTK Query client generated from the OpenAPI contract, MSW over the contract mocks, hardened nginx image, Postgres and a Caddy HTTPS gateway in per-module compose files

## Outcome / lesson

Contract-first client: hand-written requests are not needed. Docker Hub rate-limited anonymous pulls, so images come from the official AWS ECR mirror
