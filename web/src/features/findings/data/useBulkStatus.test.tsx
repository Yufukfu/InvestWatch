import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import * as generated from '../../../api/generated';
import findings from '../../../test/fixtures/findings.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useBulkStatus } from './useBulkStatus';

const [a, b] = findings.items;
const MISSING = '00000000-0000-4000-8000-000000000000';

describe('useBulkStatus', () => {
  it('sends the ids in order with the status and maps each result, naming a missing one by its sent title', async () => {
    let body: unknown;
    server.use(
      http.post('http://localhost/api/findings/bulk-status', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          updated: 1,
          not_found: 1,
          results: [
            { id: a.id, result: 'updated', finding: { ...a, status: 'confirmed', title: 'Nowy tytuł' } },
            { id: MISSING, result: 'not_found', finding: null },
          ],
        });
      }),
    );
    const { result } = renderHook(() => useBulkStatus(), { wrapper: storeWrapper() });
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.apply(
        [
          { id: a.id, title: a.title },
          { id: MISSING, title: 'Usunięte' },
        ],
        'confirmed',
      );
    });
    expect(ok).toBe(true);
    expect(body).toEqual({ ids: [a.id, MISSING], status: 'confirmed' });
    expect(result.current.outcome).toEqual({
      status: 'confirmed',
      updated: 1,
      notFound: 1,
      items: [
        { id: a.id, title: 'Nowy tytuł', result: 'updated' },
        { id: MISSING, title: 'Usunięte', result: 'not_found' },
      ],
    });
    expect(result.current.error).toBeUndefined();
  });

  it('reports a Polish error and no outcome when the request fails', async () => {
    server.use(http.post('http://localhost/api/findings/bulk-status', () => HttpResponse.json({ error: 'too many ids' }, { status: 422 })));
    const { result } = renderHook(() => useBulkStatus(), { wrapper: storeWrapper() });
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.apply([{ id: a.id, title: a.title }], 'closed');
    });
    expect(ok).toBe(false);
    expect(result.current.error).toEqual({ message: 'serwer odrzucił tę wartość.', detail: 'too many ids' });
    expect(result.current.outcome).toBeUndefined();
  });

  it('a new request clears the previous outcome and error; dismiss clears the outcome', async () => {
    let fail = true;
    server.use(
      http.post('http://localhost/api/findings/bulk-status', () =>
        fail
          ? HttpResponse.error()
          : HttpResponse.json({ updated: 1, not_found: 0, results: [{ id: b.id, result: 'updated', finding: b }] }),
      ),
    );
    const { result } = renderHook(() => useBulkStatus(), { wrapper: storeWrapper() });
    await act(async () => void (await result.current.apply([{ id: b.id, title: b.title }], 'closed')));
    expect(result.current.error?.message).toBe('brak połączenia z serwerem.');
    fail = false;
    await act(async () => void (await result.current.apply([{ id: b.id, title: b.title }], 'closed')));
    expect(result.current.error).toBeUndefined();
    expect(result.current.outcome?.updated).toBe(1);
    act(() => result.current.dismiss());
    expect(result.current.outcome).toBeUndefined();
  });

  it('a successful change refetches the findings list, the summary and the calibration', async () => {
    let listCalls = 0;
    let summaryCalls = 0;
    let calibrationCalls = 0;
    server.use(
      http.get('http://localhost/api/calibration', () => {
        calibrationCalls += 1;
        return HttpResponse.json({ module: 'M2', current_threshold: 0.5, labeled_samples: 0, points: [] });
      }),
      http.get('http://localhost/api/findings', () => {
        listCalls += 1;
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
      http.get('http://localhost/api/stats/summary', () => {
        summaryCalls += 1;
        return HttpResponse.json({ total: 0, by_module: {}, by_status: {}, by_platform: {}, by_risk_level: {} });
      }),
      http.post('http://localhost/api/findings/bulk-status', () =>
        HttpResponse.json({ updated: 1, not_found: 0, results: [{ id: a.id, result: 'updated', finding: a }] }),
      ),
    );
    const { result } = renderHook(
      () => {
        generated.useGetFindingsQuery({});
        generated.useGetStatsSummaryQuery();
        generated.useGetCalibrationQuery({ module: 'M2' });
        return useBulkStatus();
      },
      { wrapper: storeWrapper() },
    );
    await waitFor(() => expect([listCalls, summaryCalls, calibrationCalls]).toEqual([1, 1, 1]));
    await act(async () => void (await result.current.apply([{ id: a.id, title: a.title }], 'confirmed')));
    await waitFor(() => expect([listCalls, summaryCalls, calibrationCalls]).toEqual([2, 2, 2]));
  });
});
