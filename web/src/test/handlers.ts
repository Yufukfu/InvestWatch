// Vitest-only MSW handlers over the contract mocks (snapshot of contracts/mocks, see scripts/sync-contracts.mjs).
// The running app always talks to the backend (the api, or contracts/mock-server); only the tests fake the network,
// and only for the routes they render. Responses are the contract mocks unchanged: the web app computes nothing the
// backend owns. A test that needs another response (for example bucket=day) overrides the route with server.use.
import { http, HttpResponse } from 'msw';
import findings from './fixtures/findings.json';
import health from './fixtures/health.json';
import summary from './fixtures/summary.json';
import trend from './fixtures/trend.json';

export const handlers = (base: string) => [
  http.get(`${base}/health`, () => HttpResponse.json(health)),
  http.get(`${base}/findings`, () => HttpResponse.json(findings)),
  http.get(`${base}/stats/summary`, () => HttpResponse.json(summary)),
  http.get(`${base}/stats/trend`, () => HttpResponse.json(trend)),
];
