# web

Dashboard: findings with filters, trend charts, real-time alerts, threshold calibration panel.

- **Owner:** B
- **Stack:** Vite, React 19, TypeScript, Redux Toolkit + RTK Query (generated client), MSW for mocks, Vitest.
- **Status:** foundation (app shell, generated client, mock mode, container). Features come next.

## Run

```bash
cd web
npm ci
cp .env.example .env.local     # VITE_USE_MOCKS=true: works without the api
npm run dev                    # http://localhost:5173
```

With `VITE_USE_MOCKS=false` the dev server proxies `/api` and `/socket.io` to `API_PROXY_TARGET`.
In docker the app is served by unprivileged nginx behind the gateway: `docker compose up --build` from the repo root, then https://localhost:8443.

## API client (contract-first)

`contracts/openapi.yaml` (owner C) is the source of truth. The web app never hand-writes requests:

```bash
npm run api:generate     # sync the contract snapshot + regenerate src/api/generated.ts
npm run contracts:check  # fails if the committed snapshot is behind contracts/
```

The snapshot (`src/api/openapi.json`, `src/mocks/fixtures/`) and `src/api/generated.ts` are committed, so `web/` builds and deploys on its own, without the rest of the repo. Never edit them by hand.

## Scripts

| Script | Does |
|---|---|
| `dev`, `build`, `preview` | Vite |
| `typecheck`, `lint`, `test` | `tsc -b`, oxlint (warnings fail), Vitest |
| `api:generate`, `contracts:sync`, `contracts:check` | contract snapshot and client |

## Security

- Only `VITE_*` variables reach the bundle, and everything in the bundle is public: no secrets in `web/`.
- Scraped content is rendered as React text, never as HTML.
- Strict CSP (`script-src 'self'`, no inline), `nosniff`, `frame-ancestors 'none'`, read-only container, non-root, no capabilities; `console.*` is stripped from production builds.
