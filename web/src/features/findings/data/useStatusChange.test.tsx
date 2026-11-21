import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import * as generated from '../../../api/generated';
import detail from '../../../test/fixtures/finding-detail.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useStatusChange } from './useStatusChange';

describe('useStatusChange', () => {
  it('sends the PATCH body and reports success', async () => {
    let body: unknown;
    server.use(
      http.patch('http://localhost/api/findings/:id', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...detail, status: 'confirmed' });
      }),
    );
    const { result } = renderHook(() => useStatusChange(detail.id), { wrapper: storeWrapper() });
    act(() => result.current.save({ status: 'confirmed', note: 'ok' }));
    await waitFor(() => expect(result.current.saved).toBe(true));
    expect(body).toEqual({ status: 'confirmed', note: 'ok' });
    expect(result.current.error).toBeUndefined();
  });

  it.each([
    [404, 'zgłoszenie już nie istnieje.'],
    [409, 'zgłoszenie zmieniło się w międzyczasie, odśwież widok.'],
    [500, 'błąd serwera, spróbuj ponownie.'],
  ])('maps HTTP %i to a Polish message', async (code, message) => {
    server.use(http.patch('http://localhost/api/findings/:id', () => HttpResponse.json({ error: 'x' }, { status: code })));
    const { result } = renderHook(() => useStatusChange(detail.id), { wrapper: storeWrapper() });
    act(() => result.current.save({ status: 'closed' }));
    await waitFor(() => expect(result.current.error?.message).toBe(message));
  });

  it('exposes the API error message on a 422', async () => {
    server.use(http.patch('http://localhost/api/findings/:id', () => HttpResponse.json({ error: 'invalid status' }, { status: 422 })));
    const { result } = renderHook(() => useStatusChange(detail.id), { wrapper: storeWrapper() });
    act(() => result.current.save({ status: 'closed' }));
    await waitFor(() => expect(result.current.error).toEqual({ message: 'serwer odrzucił tę wartość.', detail: 'invalid status' }));
    expect(result.current.saved).toBe(false);
  });

  it('gives a generic message when the network fails', async () => {
    server.use(http.patch('http://localhost/api/findings/:id', () => HttpResponse.error()));
    const { result } = renderHook(() => useStatusChange(detail.id), { wrapper: storeWrapper() });
    act(() => result.current.save({ status: 'closed' }));
    await waitFor(() => expect(result.current.error).toEqual({ message: 'brak połączenia z serwerem.', detail: undefined }));
  });

  it('a successful change refetches the findings list and the summary', async () => {
    let listCalls = 0;
    let summaryCalls = 0;
    server.use(
      http.get('http://localhost/api/findings', () => {
        listCalls += 1;
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
      http.get('http://localhost/api/stats/summary', () => {
        summaryCalls += 1;
        return HttpResponse.json({ total: 0, by_module: {}, by_status: {}, by_platform: {}, by_risk_level: {} });
      }),
      http.patch('http://localhost/api/findings/:id', () => HttpResponse.json(detail)),
    );
    const wrapper = storeWrapper();
    const { result } = renderHook(
      () => {
        const { useGetFindingsQuery, useGetStatsSummaryQuery } = generated;
        useGetFindingsQuery({});
        useGetStatsSummaryQuery();
        return useStatusChange(detail.id);
      },
      { wrapper },
    );
    await waitFor(() => expect(listCalls).toBe(1));
    await waitFor(() => expect(summaryCalls).toBe(1));
    act(() => result.current.save({ status: 'closed' }));
    await waitFor(() => expect(listCalls).toBe(2));
    await waitFor(() => expect(summaryCalls).toBe(2));
  });
});
