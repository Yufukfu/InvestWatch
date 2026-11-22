import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import summary from '../../../test/fixtures/summary.json';
import { server } from '../../../test/setup';
import { useGetStatsSummaryQuery } from '../../../api/generated';
import { storeWrapper } from '../../../test/store';
import { useSummary } from './useSummary';

describe('useSummary', () => {
  it('is undefined until data arrives, then maps the contract mock', async () => {
    const { result } = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    expect(result.current).toBeUndefined();
    await waitFor(() => expect(result.current).toBeDefined());
    expect(result.current).toEqual({
      total: summary.total,
      highRisk: summary.by_risk_level.high,
      newCount: summary.by_status.new,
      byModule: [
        { module: 'M1', count: 4 },
        { module: 'M2', count: 3 },
        { module: 'M3', count: 4 },
      ],
    });
  });

  it('orders the module counts by module name and tolerates a missing by_module', async () => {
    server.use(
      http.get('http://localhost/api/stats/summary', () =>
        HttpResponse.json({ ...summary, by_module: { M3: 1, M1: 2 } }),
      ),
    );
    const first = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    await waitFor(() => expect(first.result.current).toBeDefined());
    expect(first.result.current?.byModule).toEqual([
      { module: 'M1', count: 2 },
      { module: 'M3', count: 1 },
    ]);

    server.use(
      http.get('http://localhost/api/stats/summary', () => HttpResponse.json({ ...summary, by_module: undefined })),
    );
    const second = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    await waitFor(() => expect(second.result.current).toBeDefined());
    expect(second.result.current?.byModule).toEqual([]);
  });

  it('defaults a missing count to 0', async () => {
    server.use(
      http.get('http://localhost/api/stats/summary', () =>
        HttpResponse.json({ ...summary, by_risk_level: {}, by_status: {} }),
      ),
    );
    const { result } = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current).toBeDefined());
    expect(result.current).toMatchObject({ total: summary.total, highRisk: 0, newCount: 0 });
  });

  it('stays undefined once the request has failed', async () => {
    server.use(http.get('http://localhost/api/stats/summary', () => HttpResponse.error()));
    // Read the query status next to the hook so the test waits for the failure instead of sleeping.
    const { result } = renderHook(() => ({ summary: useSummary(), query: useGetStatsSummaryQuery() }), {
      wrapper: storeWrapper(),
    });
    await waitFor(() => expect(result.current.query.isError).toBe(true));
    expect(result.current.summary).toBeUndefined();
  });
});
