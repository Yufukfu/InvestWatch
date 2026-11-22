---
when: Sun ~06:30
who: Adam
---

## What was done with AI

A Claude Code session rehearsed `main` 313c625b end to end: web checks, API and analytics tests in a Python 3.12 container, a cold `docker compose up`, the dashboard through a browser tool, the renderer and a scheduled scan.

## Outcome / lesson

The renderer rehearsal showed rendering is not demo-safe when several scans start at once, so it stays off by default and the enabling line is documented. Docker's default address pools were exhausted by leftover test stacks: a compose override with explicit subnets let the stack start without touching other projects.
