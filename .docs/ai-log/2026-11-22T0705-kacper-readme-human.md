---
when: Sun 07:05
who: Kacper
---

## What was done with AI

After #163, the human asked for a README written in plain language ("po ludzku"). The same Claude Code session rewrote the root `README.md` for a reader who opens the repository for the first time. It added a short description of M1–M3, turned the Quick Start into numbered steps, and replaced the wall of variable names with two short tables: what you would change, and what each service does and lets you configure. The full per-service variable list (#75) moved into a collapsed `<details>` block, with its content unchanged. The service descriptions were checked against the code first, for example that MinIO holds scraped HTML and screenshots (`scraper/src/iw_scraper/ingest/storage.py`).

## Outcome / lesson

The variable coverage diff against the compose files was rerun: every `${VAR}` is still named and none was dropped. Lesson: #163 fixed the facts but kept the structure, and the structure was what read as robotic. Leading with what a reader does and wants to change, and putting the exhaustive list behind `<details>`, kept #75's completeness without making it the first thing a reader sees.
