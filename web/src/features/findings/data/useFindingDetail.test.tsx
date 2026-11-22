import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import detail from '../../../test/fixtures/finding-detail.json';
import { server } from '../../../test/setup';
import { makeStore, storeWrapper } from '../../../test/store';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { investWatchApi } from '../../../api/generated';
import { useFindingDetail } from './useFindingDetail';

describe('useFindingDetail', () => {
  it('requests nothing without an id', () => {
    const { result } = renderHook(() => useFindingDetail(undefined), { wrapper: storeWrapper() });
    expect(result.current).toEqual({ detail: undefined, isLoading: false, isError: false, notFound: false });
  });

  it('maps the detail mock to the view model', async () => {
    const { result } = renderHook(() => useFindingDetail(detail.id), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.detail).toBeDefined());
    const d = result.current.detail!;
    expect(d.title).toBe(detail.title);
    expect(d.documentId).toBe(detail.document_id);
    expect(d.riskLevel).toBe(detail.risk_level);
    expect(d.firm).toEqual({
      name: detail.firm.name,
      authorized: detail.firm.authorized,
      registryType: detail.firm.registry_type,
      matchConfidence: detail.firm.match_confidence,
    });
    expect(d.rules).toHaveLength(detail.rules.length);
    expect(d.rules[2]).toEqual({
      ruleId: detail.rules[2].rule_id,
      name: detail.rules[2].name,
      result: detail.rules[2].result,
      severity: detail.rules[2].severity,
      evidence: detail.rules[2].evidence,
      explanation: detail.rules[2].explanation,
      legalBasis: detail.rules[2].legal_basis,
      method: detail.rules[2].method,
    });
    expect(d.screenshotUrl).toBe(detail.screenshot_urls.desktop);
    expect(d.documentText).toBe(detail.document.text);
    expect(d.llm).toBe(detail.model.llm);
    expect(d.exportUrl).toBe(`http://localhost/api/findings/${detail.id}/export?format=html`);
  });

  it('has no re-scan state for the contract mock, which carries no scrape_meta.rescan', async () => {
    const { result } = renderHook(() => useFindingDetail(detail.id), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.detail).toBeDefined());
    expect(result.current.detail!.rescan).toBeUndefined();
  });

  it('maps document.scrape_meta.rescan from the api to the view model', async () => {
    const latest = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
    const withRescan = {
      ...detail,
      document: {
        ...detail.document,
        scrape_meta: { ...detail.document.scrape_meta, rescan: { state: 'changed', latest_document_id: latest, checked_at: '2026-11-22T06:00:00Z' } },
      },
    };
    server.use(http.get('http://localhost/api/findings/:id', () => HttpResponse.json(withRescan)));
    const { result } = renderHook(() => useFindingDetail(detail.id), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.detail).toBeDefined());
    expect(result.current.detail!.rescan).toEqual({ state: 'changed', latestDocumentId: latest, checkedAt: '2026-11-22T06:00:00Z' });
  });

  it('reports notFound on a 404', async () => {
    const { result } = renderHook(() => useFindingDetail('00000000-0000-4000-8000-000000000000'), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.notFound).toBe(true));
    expect(result.current.isError).toBe(true);
    expect(result.current.detail).toBeUndefined();
  });

  it('a server error is an error but not "not found"', async () => {
    server.use(http.get('http://localhost/api/findings/:id', () => HttpResponse.json({ error: 'boom' }, { status: 500 })));
    const { result } = renderHook(() => useFindingDetail(detail.id), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.notFound).toBe(false);
  });

  it('never shows the previous finding while another id loads', async () => {
    const { result, rerender } = renderHook(({ id }) => useFindingDetail(id), {
      wrapper: storeWrapper(),
      initialProps: { id: detail.id as string },
    });
    await waitFor(() => expect(result.current.detail?.id).toBe(detail.id));
    rerender({ id: '00000000-0000-4000-8000-000000000000' });
    expect(result.current.detail).toBeUndefined();
    await waitFor(() => expect(result.current.notFound).toBe(true));
    expect(result.current.detail).toBeUndefined();
  });

  it('keeps the last detail when a refetch fails', async () => {
    let fail = false;
    server.use(http.get('http://localhost/api/findings/:id', () => (fail ? HttpResponse.json({ error: 'x' }, { status: 500 }) : HttpResponse.json(detail))));
    const store = makeStore();
    const { result } = renderHook(() => useFindingDetail(detail.id), {
      wrapper: ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>,
    });
    await waitFor(() => expect(result.current.detail).toBeDefined());
    fail = true;
    act(() => {
      store.dispatch(investWatchApi.util.invalidateTags(['findings']));
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.detail?.id).toBe(detail.id);
  });
});
