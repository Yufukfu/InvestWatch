---
when: Sun ~02:20
who: Damian
---

## What was done with AI

A Claude Code session added the contract 1.2.0 evidence pack route (`GET /findings/{id}/export`, issue #70) to the mock server, so the dashboard's "Eksportuj" button works in mock mode. It copied the api's `evidence.py` instead of writing a second renderer, and checked every mock finding's pack against the contract and against its own detail.

## Outcome / lesson

Branch `contracts/mock-finding-export`, OpenSpec change of the same name. The mock server has no object store, so `raw` is always reported unavailable rather than filled with made-up HTML: a fake raw page would look like evidence. The mock tests' copy of `openapi_check.py` needed the same fragment-ref fix as the api's.
