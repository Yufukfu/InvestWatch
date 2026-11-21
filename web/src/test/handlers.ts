// Vitest-only MSW handlers over the contract mocks (snapshot of contracts/mocks, see scripts/sync-contracts.mjs).
// The running app always talks to the backend (the api, or contracts/mock-server); only the tests fake the network,
// and only for the routes they render. Responses are the contract mocks unchanged: the web app computes nothing the
// backend owns. A test that needs another response (for example bucket=day) overrides the route with server.use.
import { http, HttpResponse } from 'msw';
import calM1 from './fixtures/calibration-M1.json';
import calM2 from './fixtures/calibration-M2.json';
import calM3 from './fixtures/calibration-M3.json';
import findingDetail from './fixtures/finding-detail.json';
import findings from './fixtures/findings.json';
import health from './fixtures/health.json';
import summary from './fixtures/summary.json';
import thresholds from './fixtures/thresholds.json';
import trend from './fixtures/trend.json';

const calibration: Record<string, typeof calM2> = { M1: calM1, M2: calM2, M3: calM3 };

export const handlers = (base: string) => [
  http.get(`${base}/health`, () => HttpResponse.json(health)),
  http.get(`${base}/findings`, () => HttpResponse.json(findings)),
  // Only the finding that has a detail mock resolves; any other id is a 404 like the backend's unknown id.
  http.get(`${base}/findings/:id`, ({ params }) =>
    params.id === findingDetail.id
      ? HttpResponse.json(findingDetail)
      : HttpResponse.json({ error: 'finding not found' }, { status: 404 }),
  ),
  http.get(`${base}/stats/summary`, () => HttpResponse.json(summary)),
  http.get(`${base}/calibration`, ({ request }) => {
    const m = new URL(request.url).searchParams.get('module') ?? '';
    return m in calibration ? HttpResponse.json(calibration[m]) : HttpResponse.json({ error: 'module required' }, { status: 422 });
  }),
  http.get(`${base}/settings/thresholds`, () => HttpResponse.json(thresholds)),
  // Hour data only: a test that asks for bucket=day must register its own day points with server.use,
  // so a forgotten override fails loudly instead of drawing hour-shaped data under "Dzień".
  http.get(`${base}/stats/trend`, ({ request }) =>
    new URL(request.url).searchParams.get('bucket') === 'day'
      ? HttpResponse.json({ error: 'no default day data in the test network' }, { status: 500 })
      : HttpResponse.json(trend),
  ),
];
