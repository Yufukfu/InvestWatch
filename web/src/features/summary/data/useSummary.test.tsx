import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import summary from '../../../mocks/fixtures/summary.json';
import { server } from '../../../test/setup';
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
    });
  });

  it('defaults a missing count to 0', async () => {
    server.use(
      http.get('http://localhost/api/stats/summary', () =>
        HttpResponse.json({ ...summary, by_risk_level: {}, by_status: {} }),
      ),
    );
    const { result } = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current).toBeDefined());
    expect(result.current).toEqual({ total: summary.total, highRisk: 0, newCount: 0 });
  });

  it('stays undefined when the request fails', async () => {
    let hit = false;
    server.use(
      http.get('http://localhost/api/stats/summary', () => {
        hit = true;
        return HttpResponse.error();
      }),
    );
    const { result } = renderHook(() => useSummary(), { wrapper: storeWrapper() });
    await waitFor(() => expect(hit).toBe(true));
    await new Promise((r) => setTimeout(r, 50));
    expect(result.current).toBeUndefined();
  });
});
