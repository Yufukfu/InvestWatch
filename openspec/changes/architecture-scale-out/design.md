# Design

## Context

See proposal.md for why. State on `origin/main` (082736c), checked in the compose files and code:

- No service has `container_name`, `deploy.replicas` or a host port except `gateway`. The scraper `worker` carries the only scale comment ("`--scale worker=N`: the queue, run lock and domain limits are shared through Redis"); `scheduler` is required to stay at one (`scraper-deployment` spec).
- `analytics` takes its Redis consumer name from `WORKER_CONSUMER`, default the container hostname (`config.py`), so replicas get distinct consumers in the same group. Redis-side state it uses (LLM cache, MinHash near-dup groups, `iw:stats:gate`) is shared across replicas; whether the near-dup grouping stays correct under two writers is **not verified** and is the first thing the run checks.
- The LLM breaker and per-document budget live in each analytics process, so M replicas multiply concurrent hosted-LLM calls. The #78 rehearsal already saw 503s from the hosted model with one replica.
- The gateway routes `/api` and `/socket.io` to `api:8000` with a plain `reverse_proxy`. The web client uses Socket.IO's default transports (HTTP long-polling, then upgrade; `web/src/features/alerts/data/socket.ts`, with a test that a blocked WebSocket must not mean no events). Polling needs every request of a session on the same replica, so `api` replicas behind a plain proxy can break realtime. Each `api` replica relays `iw:events` to its own clients, so fan-out itself is not the problem.
- `infra/tests/smoke.sh` is not run by CI; it is run by hand before `infra/` changes.

## Goals / Non-Goals

**Goals:**
- A statement of scalability that a jury member can reproduce with one command and that we ran ourselves.
- A diagram that cannot drift silently from the compose files.
- Minimal changes to services: fix only what the run proves broken for a service we claim.

**Non-Goals:**
- Multi-host deployment, orchestrators, autoscaling, scaling the data stores, benchmarking beyond one measured before/after.
- Changing any contract, route or event.

## Decisions

1. **Claim only what a run shows.** The table has three outcomes per service: scalable (run with N>1, evidence recorded), single-instance by construction (host port, one-shot, data store), single-instance because the run found a problem (reason stated). Alternative: claim scalability from reading the code. Rejected: the criterion is demonstrated scalability and the code reading already missed the Socket.IO polling case.
2. **`api` scaling is a stretch with a hard gate.** Default outcome: `api` listed single-instance with the Socket.IO reason. If time allows, try two replicas with the gateway discovering all replica addresses (Caddy `dynamic a` upstreams, since a hostname upstream is resolved to one address) plus a stickiness policy, or a websocket-only client transport (a `web/` change, so Kacper's own code). Alternatives: sticky routing in Caddy (infra only, but needs the dynamic upstreams checked), websocket-only transport (breaks the "blocked WebSocket still works" test and requirement), leave single (cheapest, honest). Recommended: leave single unless the run shows a cheap, tested fix. A gateway change becomes an ADR in this change's PR.
3. **Diagram as text in the slide file.** A Mermaid or ASCII block in `.docs/presentation-architecture.md`, which the team already uses for slide sources, not an image and not in the README (issue default). The service and network lists are generated from `docker compose config` for the check, so the diagram and the compose files are compared by command, not by eye. Alternative: an image from a design tool. Rejected: cannot be diffed or checked.
4. **One probe in `smoke.sh`, not a new test harness.** Reuse the throwaway-project mechanism the file has.
5. **LLM caveat is part of the claim.** The runbook says analytics replicas help rules-only and hosted-LLM runs only as far as the provider allows, and that the local `ollama` profile is one instance with a CPU limit, so more `analytics` replicas do not add LLM throughput there.

## Risks / Trade-offs

- A replica run needs the full stack and enough RAM; the sums of the compose limits for `--scale worker=3 --scale analytics=2` go to #75 and into the notes. If the demo machine cannot hold it, the slide says "run on <machine>" and shows the recorded output.
- The run may show a duplicate or lost result under two analytics replicas (near-dup groups, stats counters). Then the fix belongs to analytics (Damian's code): this change opens an issue for him and documents analytics as single-instance until it is fixed, instead of editing his module.
- Throughput numbers are noisy on a laptop and depend on target sites and the LLM; one before/after on the same input set, or none.

## Open Questions

- Does Kacper want `api` scaling attempted (decision 2) or documented single from the start? Default here: attempt only after the worker and analytics rows are done, and only if the fix is small.
