## Why

Review of PR #6 (Damian) found a flaky test, a dev-proxy setting that was silently ignored, and gateway gaps. Fixing them before merge keeps the foundation trustworthy for feature work.

## What Changes

- `contracts:check` tests run on temp copies (`IW_WEB_DIR`, `IW_CONTRACTS_DIR`) instead of mutating the real `src/api/generated.ts`, so parallel test files never see a broken client and an interrupted run leaves nothing behind.
- `vite.config.ts` reads `API_PROXY_TARGET` through `loadEnv`, so `.env`/`.env.local` work as `web/README.md` says.
- The health badge tells "the API reports the system down" (`System nie działa`) apart from "no answer from the API" (`Brak połączenia z API`).
- Gateway: serves `127.0.0.1` as well as `IW_HOSTNAME` (with `default_sni` for clients that send no SNI); bare `/api` and `/socket.io` reach the api instead of the SPA; HSTS off by default (`max-age=0`) because it ignores ports.
- `infra/CLAUDE.md` plus rows in the root `CLAUDE.md` and `.docs/INDEX.md`; unused `react-router` and `socket.io-client` removed; a single typecheck in the Docker build.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `web-foundation`: health badge distinguishes system-down from API-unreachable.

## Impact

- Owner: Kacper (`web/`, `infra/`). Touches no contract, REST route or event.
- Out of scope: everything else in the review is covered above; no open items.
