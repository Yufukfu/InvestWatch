# Follow-ups: web-setup

Findings from the whole-branch `iw-reviewer` pass (security focus) that are out of scope or need another owner.

| Item | Disposition |
|---|---|
| HSTS on `localhost` would pin https on every local port | fix-here: `IW_HSTS` env, default `max-age=300` |
| `contracts:check` ignored a stale `generated.ts` and orphan fixtures | fix-here: both checked, with tests |
| Plain-text rendering test could not fail; no API-down test | fix-here: XSS payload and API-down tests, mutation-checked |
| HTTP redirect hardcoded port 8443 | fix-here: `{$IW_HTTPS_PORT}` |
| `init-env.sh` could write empty passwords if `openssl` failed | fix-here: length check before writing |
| `.env.example` shipped `change-me` passwords | fix-here: empty values, compose refuses to start |
| Dotfile 403 without security headers | fix-here |
| Default privileges only cover tables created by `iw_admin` | docs: `infra/README.md` says to run Alembic as `iw_admin` (Damian) |
| CSP/headers on `api` responses, Socket.IO over `wss` under `connect-src 'self'` | new-item: verify when `api` exists (Integration #1) |
| App password visible via `docker inspect` (official image pattern) | wont-fix: local single-host stack; Docker secrets if deployed shared |
