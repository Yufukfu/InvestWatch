---
when: Sat ~17:30
who: Damian
---

## What was done with AI

Claude Code session (started by the coordinating session) proposed and applied `infra-compose`: Redis, object storage with `iw-raw`, the `llm` Ollama profile, project-scoped networks, `egress`, a loopback dev-ports override, all test-first against throwaway compose projects (`infra/tests/smoke.sh`) with a mutation check and a fresh reviewer agent per task group

## Outcome / lesson

Branch `chore/infra-compose`. The brief assumed no compose existed; the agent found ADR 0202's layout on `main` and built on it. Registry checks showed upstream MinIO images are gone (ADR 0306). Reviewers caught real bugs the author missed: a `printf` pipe into `exec redis-server` left `sh` as PID 1 so Redis never got SIGTERM, a CRLF `.env.example` silently left secrets empty, and the claim that only `egress` reaches the internet (`edge` cannot be internal). One new test turned out unable to fail (Redis rewrites its argv) and was dropped. Lesson: run a mutant against every new check, including the ones written to pin review fixes
