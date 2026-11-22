---
when: Sun 03:11
who: Kacper
---

## What was done with AI

A sub-agent wrote the root README hardware requirements and configuration table for issue #75. Prompt: base every number on evidence (compose limits, image sizes, published model sizes) and say how it was obtained; compare the config table against compose files, `.env.example` files and the env reads in the code.

## Outcome / lesson

Branch `chore/readme-hardware`. The agent built the images and started part of the stack for `docker stats` on an 8 GB machine already running other stacks; the coordinator stopped it for memory pressure, and the numbers come from static sources plus one idle sample. The code comparison found variables compose never forwards (analytics `OFFICIAL_SOURCE_DOMAINS`, `MAX_DOCUMENT_BYTES`, scraper `SCRAPER_*` tuning, `RENDER_MAX_BLOCKS`), now listed in the README; `VITE_EVENTS_URL` was missing from `web/.env.example`. Lesson: on a shared demo machine, measure from limits and manifests, not by running the stack.
