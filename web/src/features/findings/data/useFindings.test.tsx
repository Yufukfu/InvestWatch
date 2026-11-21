import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import findings from '../../../mocks/fixtures/findings.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useFindings } from './useFindings';

describe('useFindings', () => {
  it('is loading first, then maps the contract mock to rows', async () => {
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.rows).toBeDefined());
    expect(result.current.isError).toBe(false);
    expect(result.current.rows).toEqual(
      findings.items.map((f) => ({
        id: f.id,
        module: f.module,
        title: f.title,
        platform: f.platform,
        score: f.score,
        status: f.status,
      })),
    );
  });

  it('requests the first page of 50', async () => {
    let query = '';
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        query = new URL(request.url).search;
        return HttpResponse.json(findings);
      }),
    );
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.rows).toBeDefined());
    const params = new URLSearchParams(query);
    expect(params.get('page')).toBe('1');
    expect(params.get('page_size')).toBe('50');
  });

  it('reports isError when the request fails', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    const { result } = renderHook(() => useFindings(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.rows).toBeUndefined();
  });
});
