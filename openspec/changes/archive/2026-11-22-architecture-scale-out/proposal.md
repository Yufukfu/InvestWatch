# Proposal

## Why

Issue #74: the architecture criterion (20%) scores module composition, scalability and openness to extension. Damian's analytics slides (#80, `.docs/presentation-analytics.md`) and Adam's scraper slides (PR #98) already show the "add a rule" and "add a collector" examples. What is left is the infra part, owned by Kacper: one architecture diagram and a documented, **verified** scale-out step with a statement of what is safe to scale. Today the only scale claim is a comment on the scraper `worker` ("`--scale worker=N`") and a sentence in `infra/README.md`; nothing was run with more than one replica, and the web client's Socket.IO transport makes `api` scaling non-obvious (see design).

## What Changes

- Add one architecture diagram (services, Redis stream and pub/sub, Postgres, object storage, the three networks, the gateway, the optional Ollama profile) for the presentation PDF, drawn from the compose files, not from the older integration-plan sketch.
- Run `docker compose up --scale worker=N --scale analytics=M` on the real stack, record what happens, and write the scale-out runbook: the command, how to see the replicas working (`docker compose ps`, `XINFO CONSUMERS iw:documents analytics`, the queue), and a table of every service marked scalable or single-instance with the reason.
- Fix whatever the run shows is broken for the services we claim as scalable. Services the run shows are not safely scalable are documented as single-instance, not patched in this change, unless the fix is one line.
- Add a scale probe to `infra/tests/smoke.sh` so the claim stays checked.
- Write the two slides (architecture, scale-out) as `.docs/presentation-architecture.md`, in the format of the other two presentation files, so Kacper pastes all three into the deck. Hardware numbers for the scaled stack are handed to issue #75, not invented here.
- Out of scope: a load balancer rewrite, Kubernetes or Swarm manifests, autoscaling, scaling Postgres, Redis or MinIO, throughput benchmarks beyond one before/after number if the run produces it, the analytics and scraper extensibility slides (done), the Ollama swap rehearsal (Damian), the README hardware section (#75), any contract, REST route or event change (none touched).

Owner: Kacper (`infra/`, diagram, slides). Adam and Damian review the rows for their own services (`worker`, `scheduler`, `analytics`, `api`), which they own.

## Capabilities

### New Capabilities
- `scale-out`: which services run with more than one replica, how to start and observe them, and what is documented and checked as single-instance.
- `architecture-overview`: the diagram and slides that describe the stack, kept equal to the compose files.

### Modified Capabilities
<!-- None: shared-infrastructure, scraper-deployment and document-stream-worker are unchanged; scale-out only adds checks over them. -->

## Impact

- `infra/README.md` (scale-out section), `infra/tests/smoke.sh` (probe), possibly `infra/gateway/Caddyfile` (only if `api` is declared scalable, see design), `.docs/presentation-architecture.md` (new), `README.md` (one link, no diagram: the issue's default keeps the README minimal), `.docs/status/dashboard.md`, `.docs/INDEX.md`, an ADR if `api` scaling changes the gateway.
- No Python, no `web/` code, no contract.
