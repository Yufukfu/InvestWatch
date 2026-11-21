# infra (owner Kacper)

Shared infrastructure: Postgres and the Caddy HTTPS gateway. The root `compose.yaml` only `include:`s each module's own `compose.yaml`. What runs where, the roles and the TLS setup are in [`README.md`](README.md); the reasoning is in [ADR 0202](../.docs/decisions/0202-deployment-topology.md). Don't restate them here.

## Rules that are easy to get wrong

- A module adds its own `<module>/compose.yaml` and one line in the root `include:`. Don't put module services in `infra/compose.yaml`.
- Only the gateway publishes host ports. A service joins `iw-edge` to be routed and `iw-data` to reach Postgres; `iw-data` stays `internal`.
- Services connect as `iw_app` (CRUD, no DDL). Migrations run as `iw_admin`: `iw_app` gets grants only on tables `iw_admin` creates.
- `01-app-role.sh` runs only on an empty volume. A role or grant change needs `docker compose down -v` locally, plus a migration for existing databases.
- Secrets come only from `.env` (`scripts/init-env.sh`), with `${VAR:?}` in compose so a missing secret fails loudly. No defaults for passwords.
- HSTS stays off (`IW_HSTS=max-age=0`) on localhost: it ignores ports and would break every local dev server.
- Images come from `public.ecr.aws` mirrors (Docker Hub rate-limits anonymous pulls).

## Done

`docker compose up --build` starts healthy from an empty volume. `https://localhost:8443` and `https://127.0.0.1:8443` serve `web`, `/api` and `/socket.io` reach `api`, and the security headers are present.
