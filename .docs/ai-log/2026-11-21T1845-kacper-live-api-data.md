---
when: Sat ~18:45
who: Kacper
---

## What was done with AI

Asked Claude Code to drop the dashboard's in-browser mocks now that the backend serves the contract: OpenSpec change `live-api-data` on a fresh worktree from `main`, guard tests first, then removal of the MSW worker and `VITE_USE_MOCKS`, MSW kept only for Vitest, the app checked through the Vite proxy against the mock server, 6 mutants tried and 6 caught

## Outcome / lesson

The web-side day aggregation in the MSW handler duplicated what the mock server already computes; removed. The first attempt ran on a checkout 33 commits behind `main` and was redone. The first live check hit a dev server from another checkout already holding port 5173: check who owns the port before trusting a curl
