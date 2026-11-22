import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { api } from '../../../api/enhanced';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import findings from '../../../test/fixtures/findings.json';
import { server } from '../../../test/setup';
import { makeStore, storeWrapper } from '../../../test/store';
import { useAdvertisers } from './useAdvertisers';

function capture(total: number) {
  const seen: Record<string, string>[] = [];
  server.use(
    http.get('http://localhost/api/findings', ({ request }) => {
      const q = Object.fromEntries(new URL(request.url).searchParams);
      seen.push(q);
      // Each page returns the mock items with page-specific ids, so pages are distinguishable.
      const items = findings.items.map((it) => ({ ...it, id: `${q.page}-${it.id}` }));
      return HttpResponse.json({ items, total, page: Number(q.page), page_size: Number(q.page_size) });
    }),
  );
  return seen;
}

describe('useAdvertisers', () => {
  it('requests M1 findings, one page when total fits, and groups the contract mock', async () => {
    const seen = capture(findings.total);
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(seen).toHaveLength(1);
    expect(seen[0]).toEqual({ module: 'M1', page: '1', page_size: '200', sort: '-detected_at' });
    expect(result.current.loaded).toBe(findings.items.length);
    expect(result.current.total).toBe(findings.total);
    expect(result.current.rows?.map((r) => r.name).sort()).toEqual(
      ['Ekonomia na luzie', 'Finanse z Kasią', 'Jan Inwestor', 'Marek Trader'],
    );
    const marek = result.current.rows?.find((r) => r.name === 'Marek Trader');
    expect(marek?.handle).toBe('@marek_trader');
    expect(marek?.firms).toEqual([
      { key: 'facc6bd1-c728-5348-90a4-011b0972fea9', name: 'Alfa Inwestycje Dom Maklerski S.A.', count: 1 },
    ]);
  });

  it('fetches pages 2 and 3 when total needs them, never page 4', async () => {
    const seen = capture(1000);
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.loaded).toBe(3 * findings.items.length));
    expect(seen.map((q) => q.page).sort()).toEqual(['1', '2', '3']);
    expect(result.current.total).toBe(1000);
    // Findings from all three pages are grouped (ids differ per page).
    const marek = result.current.rows?.find((r) => r.name === 'Marek Trader');
    expect(marek?.count).toBe(3);
    expect(marek?.repeat).toBe(true);
  });

  it('fetches exactly two pages when total is just over one page', async () => {
    const seen = capture(201);
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.loaded).toBe(2 * findings.items.length));
    expect(seen.map((q) => q.page).sort()).toEqual(['1', '2']);
  });

  it('fetches one page when total equals the page size', async () => {
    const seen = capture(200);
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(seen.map((q) => q.page)).toEqual(['1']);
  });

  it('reports an error and no rows when the request fails', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
  });

  it('reports an error when a later page fails', async () => {
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        const page = new URL(request.url).searchParams.get('page');
        return page === '1'
          ? HttpResponse.json({ ...findings, total: 500 })
          : HttpResponse.json({ error: 'boom' }, { status: 500 });
      }),
    );
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
  });

  it('shows nothing until every needed page has arrived', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    server.use(
      http.get('http://localhost/api/findings', async ({ request }) => {
        const page = new URL(request.url).searchParams.get('page');
        if (page !== '1') await gate;
        return HttpResponse.json({ ...findings, items: findings.items.map((it) => ({ ...it, id: `${page}-${it.id}` })), total: 500 });
      }),
    );
    const { result } = renderHook(() => useAdvertisers(), { wrapper: storeWrapper() });
    // Page 1 has arrived once total is known; pages 2 and 3 are still held back.
    await waitFor(() => expect(result.current.total).toBe(500));
    expect(result.current.rows).toBeUndefined();
    expect(result.current.isLoading).toBe(true);
    release();
    await waitFor(() => expect(result.current.loaded).toBe(3 * findings.items.length));
  });

  it('hides the rows when a refetch fails after a success', async () => {
    const store = makeStore();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useAdvertisers(), { wrapper });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.json({ error: 'boom' }, { status: 500 })));
    act(() => {
      store.dispatch(api.util.invalidateTags(['findings']));
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
  });
});
