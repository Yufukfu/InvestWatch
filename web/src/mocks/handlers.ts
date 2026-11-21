// MSW handlers that serve the contract mocks (snapshot of contracts/mocks, see scripts/sync-contracts.mjs).
// Components only talk to the generated RTK Query client, so switching to the live api changes nothing in them.
import { http, HttpResponse } from 'msw';
import calibrationM1 from './fixtures/calibration-M1.json';
import calibrationM2 from './fixtures/calibration-M2.json';
import calibrationM3 from './fixtures/calibration-M3.json';
import findingDetail from './fixtures/finding-detail.json';
import findings from './fixtures/findings.json';
import health from './fixtures/health.json';
import sources from './fixtures/sources.json';
import summary from './fixtures/summary.json';
import thresholds from './fixtures/thresholds.json';
import trend from './fixtures/trend.json';

const calibration = { M1: calibrationM1, M2: calibrationM2, M3: calibrationM3 } as const;

export const handlers = (base: string) => [
  http.get(`${base}/health`, () => HttpResponse.json(health)),
  http.get(`${base}/findings`, () => HttpResponse.json(findings)),
  http.get(`${base}/findings/:id`, () => HttpResponse.json(findingDetail)),
  http.patch(`${base}/findings/:id`, async ({ params, request }) => {
    const patch = (await request.json()) as Record<string, unknown>;
    const found = findings.items.find((f) => f.id === params.id);
    return found ? HttpResponse.json({ ...found, ...patch }) : new HttpResponse(null, { status: 404 });
  }),
  http.get(`${base}/stats/summary`, () => HttpResponse.json(summary)),
  http.get(`${base}/stats/trend`, () => HttpResponse.json(trend)),
  http.get(`${base}/calibration`, ({ request }) => {
    const module = new URL(request.url).searchParams.get('module') as keyof typeof calibration | null;
    return HttpResponse.json(calibration[module ?? 'M2'] ?? calibration.M2);
  }),
  http.get(`${base}/settings/thresholds`, () => HttpResponse.json(thresholds)),
  http.put(`${base}/settings/thresholds`, async ({ request }) => HttpResponse.json(await request.json())),
  http.get(`${base}/sources`, () => HttpResponse.json(sources)),
];
