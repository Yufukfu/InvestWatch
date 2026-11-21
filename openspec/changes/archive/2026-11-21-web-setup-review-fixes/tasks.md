## 1. Web fixes

- [x] 1.1 Test: badge shows "System nie działa" for `status: down`; `contracts:check` tests run on temp copies
- [x] 1.2 HealthBadge unreachable vs down, `IW_WEB_DIR` override, `loadEnv` for `API_PROXY_TARGET`, remove unused deps, single typecheck in Docker
- [x] 1.3 Mutation check — mutations: 3 tried, 3 caught

## 2. Gateway and docs

- [x] 2.1 Caddy: `127.0.0.1` site + `default_sni`, `@api` matcher for bare `/api` and `/socket.io`, HSTS `max-age=0` default
- [x] 2.2 Verified on the stack: `https://127.0.0.1:8443` 200, bare `/api` 502 (no api yet, not the SPA), HSTS `max-age=0`, proxy target from `.env.local`
- [x] 2.3 Mutation check — mutations: n/a, config-only group (Caddyfile, compose, env); verified against the running stack
- [x] 2.4 `infra/CLAUDE.md`, root `CLAUDE.md` and `.docs/INDEX.md` rows

## 3. Closing

- [x] 3.1 Apply iw-docs-update and add the iw-ai-log row
- [x] 3.2 Run iw-pr-review and fix real findings
