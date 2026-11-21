import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import detail from '../../../test/fixtures/finding-detail.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
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
});
