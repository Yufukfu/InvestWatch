# web

Dashboard: findings with filters, trend charts, real-time alerts, threshold calibration panel.

- **Owner:** Kacper
- **Stack:** Vite, React 19, TypeScript, Redux Toolkit + RTK Query (generated client), Vitest with MSW as the test-only network fake.
- **Status:** foundation (app shell, generated client, container), data from the backend only, the trend chart (Recharts, hourly or daily buckets) and the findings workspace: filters, sort and paging in the URL (shareable links), a detail panel with the failed rules and their legal basis, and status change. Alerts and the calibration panel come next.

## Run

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev                    # http://localhost:5173
```

The app has no built-in mock data ([ADR 0206](../.docs/decisions/0206-dashboard-data-from-backend.md)): the dev server proxies `/api` and `/socket.io` to `API_PROXY_TARGET` (default `http://localhost:8000`), so run the backend there first: the contract mock server (`contracts/README.md`, "Mock server") until the api serves REST. Run it as a container:

```bash
docker build -f contracts/mock-server/Dockerfile -t iw-mock-server contracts
docker run --rm -p 127.0.0.1:8000:8000 iw-mock-server
```

The mock endpoints stay until we have sensible data. A browser that ran the old mock mode on the same origin keeps its service worker until you unregister it (DevTools, Application, Service Workers). Compose does not start a REST backend yet, so `docker compose up` alone shows only the dashboard's error states.
In docker the app is served by unprivileged nginx behind the gateway: `docker compose up --build` from the repo root, then https://localhost:8443.

## API client (contract-first)

`contracts/openapi.yaml` (owner Damian) is the source of truth. The web app never hand-writes requests:

```bash
npm run api:generate     # sync the contract snapshot + regenerate src/api/generated.ts
npm run contracts:check  # fails if the committed snapshot is behind contracts/
```

The snapshot (`src/api/openapi.json`, `src/test/fixtures/` for the Vitest MSW handlers) and `src/api/generated.ts` are committed, so `web/` builds and deploys on its own, without the rest of the repo. Never edit them by hand.

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
