# infra

Shared infrastructure, owned by B (repository layout). Each module has its own `compose.yaml`; the root `compose.yaml` only includes them, so a module is deployed, scaled or replaced without touching the others.

| Service | Purpose | Reachable from |
|---|---|---|
| `postgres` | PostgreSQL 17 | network `iw-data` only (internal: no host port, no internet). Local: `docker compose exec postgres psql -U iw_admin -d investwatch` |
| `gateway` | Caddy: the only public entry, TLS, `/api` + `/socket.io` → `api:8000`, `/` → `web:8080` | host `https://localhost:8443` (HTTP 8080 redirects) |

## Database access

- `iw_admin` (from `POSTGRES_ADMIN_*`): migrations and ops only.
- `iw_app` (from `POSTGRES_APP_*`): what services use. CRUD on tables in `public`, no DDL, no superuser.
- Connection for services on `iw-data`: `postgresql://iw_app:<password>@postgres:5432/investwatch`.
- Schema comes from migrations (Alembic in `api`, owner C), never by hand. Run migrations as `iw_admin`: `iw_app` gets CRUD automatically only on tables created by `iw_admin`. The init script runs only on an empty volume; to reset: `docker compose down -v`.

A service that needs the DB joins `iw-data` in its own compose file:

```yaml
services:
  api:
    networks: [edge, data]
networks:
  edge: { name: iw-edge }
  data: { name: iw-data, internal: true }
```

## TLS locally

Caddy issues a certificate from its own local CA (`tls internal`), so the browser warns once. To trust it on macOS:

```bash
docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./caddy-root.crt
```

## Secrets

`./scripts/init-env.sh` creates `.env` (mode 600) with random passwords. Compose refuses to start without them. `.env` is git-ignored and blocked by the commit hook.
