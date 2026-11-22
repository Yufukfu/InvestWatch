---
when: Sun ~02:30
who: Damian
---

## What was done with AI

A Claude Code side session implemented Damian's part of issue #70: a read-only evidence pack `GET /findings/{id}/export` (JSON, or a printable Polish page with `?format=html`) through the OpenSpec change `api-finding-export`, contract 1.2.0, after checking what the scraper stores in `iw-raw` and how the detail route builds its body

## Outcome / lesson

Branch `api/finding-evidence-export`. The detail body was factored out unchanged and reused, so the pack cannot drift from the dashboard's view. A MinIO outage degrades only the raw part instead of failing the export. The page escapes every stored value and sends a CSP without scripts, tested with hostile titles, quotes, URLs and screenshot keys. The test helper could not resolve `./schemas/x.json#/$defs/...` refs and was extended
