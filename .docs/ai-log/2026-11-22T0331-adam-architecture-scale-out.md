---
when: Sun 03:31
who: Adam
---

## What was done with AI

A Claude Code session turned the open infra half of issue #74 into an OpenSpec change for Kacper (`architecture-scale-out`): read the issue, `infra/`, the module compose files and the Redis producers and consumers on `main`, proposed the change with a hard "run it before documenting it" first group, then applied it: a real stack with `--scale worker=3 --scale analytics=2`, 17 scans, a replica killed mid-batch, `scheduler`, `gateway` and `api` duplicated on purpose, a before/after drain time, a smoke-test group, the runbook table and the two slides. The diagram is checked against `docker compose config` by a command, not by eye.

## Outcome / lesson

Branch `web/architecture-scale-out`. The proposal predicted that `api` replicas would break Socket.IO polling; the run showed something else (the gateway sends every request to one replica, so nothing is balanced and nothing breaks), so `api` is documented single-instance with the measured reason and no gateway change. The first replica-kill test was inconclusive (the batch finished before the kill, claim idle time is 60 s); a bigger batch and an immediate kill showed the claim path. Two slips of the agent, both caught at once: the `.env` copy from the main clone silently did nothing (there is none), and an unquoted URL with `?` was swallowed by zsh, so no scans were sent on the first try. Near-duplicate grouping under two replicas was read from the code, not forced in a run, and is stated that way. The human approves the spec and merges.
