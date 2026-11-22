---
when: Sun ~12:00
who: Adam
---

## What was done with AI

A Claude Code session fixed issue #97 autonomously: reproduced the failing `-f infra -f api -f scraper` chain with the installed Compose v5.2.0 before touching anything, tried the issue's suggested `../scraper/` include against five chains, and wrote a `stack.sh` scenario that goes red on the bare include

## Outcome / lesson

Branch `scraper/compose-include-chain`, OpenSpec change of the same name. The issue's claim that `-f scraper/compose.yaml` alone works was wrong (it fails on the undefined `data` network with or without the fix, since infra owns it); the other claims held. A mutation (bare include) turns the scenario red.
