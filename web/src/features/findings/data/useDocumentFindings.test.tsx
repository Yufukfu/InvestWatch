import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import findings from '../../../test/fixtures/findings.json';
import { server } from '../../../test/setup';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { api } from '../../../api/enhanced';
import { makeStore, storeWrapper } from '../../../test/store';
import { useDocumentFindings } from './useDocumentFindings';

// The contract mocks hold one post with an M1 and an M3 finding.
const pair = findings.items.filter((i) => findings.items.filter((x) => x.document_id === i.document_id).length > 1);
const docId = pair[0].document_id;

describe('useDocumentFindings', () => {
  it('asks for the findings of the document only, without the list filters', async () => {
    window.history.replaceState(null, '', '/?module=M1&status=new&page=2');
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json({ ...findings, items: pair, total: pair.length });
      }),
    );
    const { result } = renderHook(() => useDocumentFindings(docId), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current).toHaveLength(2));
    const p = seen.at(-1)!;
    expect(p.get('document_id')).toBe(docId);
    expect(p.get('page_size')).toBe('10');
    for (const name of ['module', 'status', 'page', 'q', 'risk_level']) expect(p.has(name)).toBe(false);
  });

  it('maps id, module and risk, ordered by module', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.json({ ...findings, items: pair, total: pair.length })));
    const { result } = renderHook(() => useDocumentFindings(docId), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current).toHaveLength(2));
    const byModule = [...pair].sort((a, b) => a.module.localeCompare(b.module));
    expect(result.current).toEqual(byModule.map((f) => ({ id: f.id, module: f.module, riskLevel: f.risk_level })));
  });

  it('drops findings of other documents when the backend ignores the parameter', async () => {
    // The default handler returns every finding, like a mock server that ignores document_id.
    const { result } = renderHook(() => useDocumentFindings(docId), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(result.current.map((o) => o.id).sort()).toEqual(pair.map((f) => f.id).sort());
  });

  it('returns nothing when the request fails', async () => {
    let calls = 0;
    server.use(
      http.get('http://localhost/api/findings', () => {
        calls += 1;
        return HttpResponse.error();
      }),
    );
    const { result } = renderHook(() => useDocumentFindings(docId), { wrapper: storeWrapper() });
    await waitFor(() => expect(calls).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 20));
    expect(result.current).toEqual([]);
  });

  it('hides the siblings when a refetch fails after a success', async () => {
    let fail = false;
    server.use(
      http.get('http://localhost/api/findings', () =>
        fail ? HttpResponse.error() : HttpResponse.json({ ...findings, items: pair, total: pair.length }),
      ),
    );
    const store = makeStore();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useDocumentFindings(docId), { wrapper });
    await waitFor(() => expect(result.current).toHaveLength(2));
    fail = true;
    act(() => {
      store.dispatch(api.util.invalidateTags(['findings']));
    });
    await waitFor(() => expect(result.current).toEqual([]));
  });

  it('sends no request without a document id', async () => {
    let calls = 0;
    server.use(
      http.get('http://localhost/api/findings', () => {
        calls += 1;
        return HttpResponse.json(findings);
      }),
    );
    const { result } = renderHook(() => useDocumentFindings(undefined), { wrapper: storeWrapper() });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
    expect(result.current).toEqual([]);
  });
});
