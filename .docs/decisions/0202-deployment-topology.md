# 0202. Deployment topology: per-module compose, HTTPS gateway, isolated database

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by Kacper via PR

## Context

The jury scores architecture at 20% (module composition, scalability, openness to extension) and requires one `docker compose up`, open source and on premise. Modules (scraper Adam, analytics Damian, api Damian, web Kacper) must be loosely coupled and deployable separately. The integration plan (§1) lists the services but not how compose is organised; three people edit in parallel, so one shared `docker-compose.yml` would be a merge-conflict hot spot.

## Options considered

1. **One root `docker-compose.yml`** with every service. Simple, but every module change edits the same file, and no module can be started alone.
2. **Per-module `compose.yaml` + root `compose.yaml` that only `include:`s them** (Compose ≥ 2.20; verified with Docker Compose v5.7.0). Each owner edits only their file; `docker compose -f web/compose.yaml up` runs one module.
3. Kubernetes / Helm. Real separation, but far beyond a 24-hour hackathon and the jury's single-command requirement.

Entry point: services publishing their own host ports (CORS between origins, several certificates) versus **one reverse proxy** routing by path. Proxy candidates: Caddy (automatic local TLS with `tls internal`, ~20-line config) and nginx/Traefik (manual certificates or label-driven config).

## Decision

Option 2, with a **Caddy gateway** as the only published entry (`https://localhost:8443`, HTTP redirects): `/api/*` and `/socket.io/*` go to `api:8000`, everything else to `web:8080`. The browser sees one origin, so there is no CORS and the Socket.IO connection is same-origin.

Shared infrastructure lives in `infra/compose.yaml` (Kacper):

- **Postgres 17** only on the network `iw-data`, declared `internal` (verified: no host port, no internet from the container). SCRAM authentication. Two roles: `iw_admin` for migrations and ops, and `iw_app` for services (CRUD on tables, no DDL; verified that `CREATE TABLE` is denied).
- Secrets only in an untracked `.env`, generated randomly by `scripts/init-env.sh`; compose refuses to start without them (`${VAR:?}`).
- Containers run with `no-new-privileges`, resource limits, and (where the image allows) read-only filesystems and no capabilities.
- Images come from the official AWS ECR mirrors (`public.ecr.aws/docker/library/*`, `public.ecr.aws/nginx/*`), because Docker Hub rate-limits anonymous pulls (observed HTTP 429 during setup).

## Consequences

- A new module adds its own `compose.yaml` and one line in the root `include:`; it joins `iw-edge` to be routed by the gateway and `iw-data` to reach the database.
- Services call each other over the internal networks by service name; only the gateway is exposed. A deployment outside compose replaces the gateway routes with the platform's ingress without code changes.
- TLS inside the stack is plain HTTP behind the gateway; mutual TLS between services is out of scope for the hackathon.
- The local CA certificate must be trusted once per machine (`infra/README.md`), or the browser warns.
- The integration plan names Damian as compose owner; with this layout Damian owns `api/compose.yaml` and `analytics/compose.yaml`, Kacper owns the root include list and `infra/`.
