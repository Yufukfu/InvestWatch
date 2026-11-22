---
when: Sat ~23:55
who: Damian
---

## What was done with AI

A Claude Code side session (from the PR #59 verification) fixed `docker compose up -d --wait` exiting 1 on the one-shot `analytics-eval`. Before choosing a fix it ran a small compose experiment on Compose v2.40 that tried each one-shot shape against `--wait`

## Outcome / lesson

Branch `analytics/eval-wait-healthcheck`. The brief's suggested fix (move the `HEALTHCHECK` into compose so the one-shot has none) was racy. `--wait` checks a service nobody depends on for "running or healthy", so a one-shot with no healthcheck passes only while it is still running and fails "exited (0)" once done. It would also have broken the `document-stream-worker` spec, which puts the `HEALTHCHECK` in the Dockerfile. The fix makes `analytics` depend on it with `service_completed_successfully, required: false` (the `api-migrate` pattern). A control run with main's file on the same stack failed "exited (0)", and the fix passed twice. Lesson: check a "likely fix" in a brief against a minimal repro before implementing it.
