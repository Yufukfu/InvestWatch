import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useHealth } from './useHealth';

describe('useHealth', () => {
  it('starts as loading, then reports the status the API returns', async () => {
    const { result } = renderHook(() => useHealth(), { wrapper: storeWrapper() });
    expect(result.current.state).toBe('loading');
    await waitFor(() => expect(result.current.state).toBe('ok'));
  });

  it('reports down when the API answers that the system is down', async () => {
    server.use(http.get('http://localhost/api/health', () => HttpResponse.json({ status: 'down', services: {} })));
    const { result } = renderHook(() => useHealth(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.state).toBe('down'));
  });

  it('reports unreachable when the request fails', async () => {
    server.use(http.get('http://localhost/api/health', () => HttpResponse.error()));
    const { result } = renderHook(() => useHealth(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.state).toBe('unreachable'));
  });

  it('reports unreachable when the answer carries no status', async () => {
    server.use(http.get('http://localhost/api/health', () => HttpResponse.json({})));
    const { result } = renderHook(() => useHealth(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.state).toBe('unreachable'));
  });
});
