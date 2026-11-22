import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import findings from '../../../test/fixtures/findings.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useFindings } from './useFindings';

function captureQuery() {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get('http://localhost/api/findings', ({ request }) => {
      seen.push(new URL(request.url).searchParams);
      return HttpResponse.json(findings);
    }),
  );
  return seen;
}

describe('useFindings', () => {
  it('is loading first, then maps the contract mock to rows and total', async () => {
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(result.current.isError).toBe(false);
    expect(result.current.total).toBe(findings.total);
    const first = findings.items[0];
    expect(result.current.rows?.[0]).toEqual({
      id: first.id,
      module: first.module,
      title: first.title,
      platform: first.platform,
      score: first.score,
      riskLevel: first.risk_level,
      status: first.status,
      detectedAt: first.detected_at,
      documentId: first.document_id,
      url: first.url,
      host: 'alfa-inwestycje.example.com',
    });
  });

  it.each([
    ['https://example.com/post/1?x=<b>', 'example.com'],
    ['http://Example.COM:8080/a', 'example.com'],
    ['javascript:alert(1)', undefined],
    ['not a url', undefined],
  ])('maps the host of %s', async (url, host) => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.json({ ...findings, items: [{ ...findings.items[0], url }] })));
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(result.current.rows?.[0].host).toBe(host);
    expect(result.current.rows?.[0].url).toBe(url);
  });

  it('sends the filters from the URL on the first request', async () => {
    window.history.replaceState(null, '', '/?module=M1&status=new,in_review&sort=-score&page=2');
    const seen = captureQuery();
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(seen).toHaveLength(1);
    expect(Object.fromEntries(seen[0])).toEqual({
      module: 'M1',
      status: 'new,in_review',
      sort: '-score',
      page: '2',
      page_size: '25',
    });
    expect(result.current.filters.module).toBe('M1');
  });

  it('a filter change updates the URL, resets the page and refetches', async () => {
    window.history.replaceState(null, '', '/?page=3');
    const seen = captureQuery();
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    act(() => result.current.setFilters({ riskLevel: 'high' }));
    expect(window.location.search).toBe('?risk_level=high');
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen[1].get('risk_level')).toBe('high');
    expect(seen[1].get('page')).toBe('1');
  });

  it('selects and clears a finding in the URL without touching the filters', async () => {
    window.history.replaceState(null, '', '/?module=M2');
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    const id = findings.items[0].id;
    act(() => result.current.select(id));
    expect(result.current.selectedId).toBe(id);
    expect(window.location.search).toBe(`?module=M2&finding=${id}`);
    act(() => result.current.select(undefined));
    expect(window.location.search).toBe('?module=M2');
  });

  it('reports isError when the request fails', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
  });

  it('requests page 1 with 25 per page by default', async () => {
    const seen = captureQuery();
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(seen[0].get('page')).toBe('1');
    expect(seen[0].get('page_size')).toBe('25');
  });

  it('keeps the last rows and total while the next result loads', async () => {
    let release: () => void = () => undefined;
    let calls = 0;
    server.use(
      http.get('http://localhost/api/findings', async () => {
        calls += 1;
        if (calls > 1) await new Promise<void>((r) => (release = r));
        return HttpResponse.json(findings);
      }),
    );
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    act(() => result.current.setFilters({ sort: '-score' }));
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.rows).toHaveLength(findings.items.length);
    expect(result.current.total).toBe(findings.total);
    act(() => release());
    await waitFor(() => expect(result.current.isFetching).toBe(false));
  });

  it('a settled search replaces the history entry; other filters push one', async () => {
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    const start = window.history.length;
    act(() => result.current.setFilters({ q: 'jan' }));
    expect(window.location.search).toBe('?q=jan');
    expect(window.history.length).toBe(start);
    act(() => result.current.setFilters({ module: 'M1' }));
    expect(window.history.length).toBe(start + 1);
    await waitFor(() => expect(result.current.isFetching).toBe(false));
  });

  it('a failed refetch clears the last rows (not shown as current)', async () => {
    let fail = false;
    server.use(http.get('http://localhost/api/findings', () => (fail ? HttpResponse.error() : HttpResponse.json(findings))));
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    fail = true;
    act(() => result.current.setFilters({ module: 'M1' }));
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
    expect(result.current.total).toBeUndefined();
  });
});
