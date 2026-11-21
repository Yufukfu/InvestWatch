import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGetFindingsByIdQuery, useGetFindingsQuery, useGetStatsSummaryQuery } from '../../../api/generated';
import detail from '../../../test/fixtures/finding-detail.json';
import findings from '../../../test/fixtures/findings.json';
import summary from '../../../test/fixtures/summary.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useRealtime } from './useRealtime';

type Handler = (payload?: unknown) => void;

const fake = vi.hoisted(() => {
  const handlers = new Map<string, Handler[]>();
  const socket = {
    on: (event: string, fn: Handler) => {
      handlers.set(event, [...(handlers.get(event) ?? []), fn]);
      return socket;
    },
    disconnect: () => {
      socket.disconnected = true;
    },
    disconnected: false,
  };
  return {
    socket,
    io: (..._args: unknown[]) => socket,
    calls: [] as unknown[][],
    fire: (event: string, payload?: unknown) => (handlers.get(event) ?? []).forEach((fn) => fn(payload)),
    reset: () => {
      handlers.clear();
      socket.disconnected = false;
    },
  };
});

vi.mock('socket.io-client', () => ({
  io: (...args: unknown[]) => {
    fake.calls.push(args);
    return fake.io(...args);
  },
}));

function countRequests() {
  const n = { list: 0, summary: 0 };
  server.use(
    http.get('http://localhost/api/findings', () => {
      n.list += 1;
      return HttpResponse.json(findings);
    }),
    http.get('http://localhost/api/stats/summary', () => {
      n.summary += 1;
      return HttpResponse.json(summary);
    }),
  );
  return n;
}

function renderWithQueries() {
  return renderHook(
    () => ({
      rt: useRealtime(),
      list: useGetFindingsQuery({ page: 1, pageSize: 25 }),
      detail: useGetFindingsByIdQuery({ id: detail.id }),
      summary: useGetStatsSummaryQuery(),
    }),
    { wrapper: storeWrapper() },
  );
}

const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

const brief = { id: findings.items[2].id, module: 'M3', score: 0.93, title: findings.items[2].title, url: 'https://x.example', platform: 'web' };

describe('useRealtime', () => {
  beforeEach(() => {
    fake.reset();
    fake.calls.length = 0;
  });
  afterEach(() => vi.useRealTimers());

  it('opens one socket to /events on /socket.io and closes it on unmount', () => {
    const { unmount } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    expect(fake.calls).toHaveLength(1);
    expect(fake.calls[0][0]).toBe('/events');
    // Default transports (polling, then upgrade): a blocked WebSocket must not mean no events.
    expect(fake.calls[0][1]).toEqual({ path: '/socket.io' });
    unmount();
    expect(fake.socket.disconnected).toBe(true);
  });

  it('reports connecting, live and offline', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    expect(result.current.connection).toBe('connecting');
    act(() => fake.fire('connect'));
    expect(result.current.connection).toBe('live');
    act(() => fake.fire('disconnect', 'transport close'));
    expect(result.current.connection).toBe('offline');
    act(() => fake.fire('connect'));
    act(() => fake.fire('connect_error', new Error('x')));
    expect(result.current.connection).toBe('offline');
  });

  it('refetches findings and stats on every connect', async () => {
    const n = countRequests();
    renderWithQueries();
    await waitFor(() => expect(n.list).toBe(1));
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire('connect'));
    await waitFor(() => expect(n.list).toBe(2));
    await waitFor(() => expect(n.summary).toBe(2));
  });

  it.each(['finding.created', 'finding.high_risk'])('%s refetches findings and stats', async (event) => {
    const n = countRequests();
    renderWithQueries();
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire(event, brief));
    await waitFor(() => expect(n.list).toBe(2));
    await waitFor(() => expect(n.summary).toBe(2));
  });

  it('finding.updated patches the cached list and detail without refetching the list', async () => {
    const n = countRequests();
    const { result } = renderWithQueries();
    await waitFor(() => expect(result.current.list.data).toBeDefined());
    await waitFor(() => expect(result.current.detail.data).toBeDefined());
    act(() => fake.fire('finding.updated', { id: detail.id, status: 'closed' }));
    await waitFor(() => expect(result.current.list.data?.items.find((i) => i.id === detail.id)?.status).toBe('closed'));
    expect(result.current.detail.data?.status).toBe('closed');
    await waitFor(() => expect(n.summary).toBe(2));
    expect(n.list).toBe(1);
  });

  it('ignores malformed payloads', async () => {
    const n = countRequests();
    const { result } = renderWithQueries();
    await waitFor(() => expect(result.current.list.data).toBeDefined());
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => {
      fake.fire('finding.updated', { id: detail.id });
      fake.fire('finding.updated', { id: detail.id, status: 'approved' });
      fake.fire('finding.created', { title: 'no id' });
      fake.fire('finding.high_risk', null);
      fake.fire('finding.high_risk', { title: 'no id' });
      fake.fire('finding.high_risk', { ...brief, id: 'not-a-uuid' });
      fake.fire('finding.created', { ...brief, id: 'not-a-uuid' });
      fake.fire('finding.updated', { id: 'not-a-uuid', status: 'closed' });
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(n.list).toBe(1);
    expect(n.summary).toBe(1);
    expect(result.current.list.data?.items.find((i) => i.id === detail.id)?.status).toBe(detail.status);
    expect(result.current.rt.alerts).toEqual([]);
  });

  it('collects high-risk alerts: newest first, one per id, at most 4', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      for (let i = 0; i < 6; i++) fake.fire('finding.high_risk', { ...brief, id: uid(i), title: `T${i}` });
      fake.fire('finding.high_risk', { ...brief, id: uid(5), title: 'T5 again' });
    });
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(5), uid(4), uid(3), uid(2)]);
    expect(result.current.alerts[0]).toEqual({ id: uid(5), module: 'M3', score: 0.93, title: 'T5 again' });
  });

  it('does not alert on finding.created', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.created', brief));
    expect(result.current.alerts).toEqual([]);
  });

  it('hides an alert after 20 seconds and on dismiss', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      fake.fire('finding.high_risk', { ...brief, id: uid(1) });
      fake.fire('finding.high_risk', { ...brief, id: uid(2) });
    });
    act(() => result.current.dismiss(uid(2)));
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(1)]);
    act(() => vi.advanceTimersByTime(19_999));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts).toEqual([]);
  });

  it('open() puts the finding in the URL and dismisses its alert', () => {
    window.history.replaceState(null, '', '/?module=M3');
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: detail.id }));
    act(() => result.current.open(detail.id));
    expect(window.location.search).toBe(`?module=M3&finding=${detail.id}`);
    expect(result.current.alerts).toEqual([]);
  });

  it('a high-risk event without a title still refreshes, but raises no toast', async () => {
    const n = countRequests();
    const { result } = renderWithQueries();
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire('finding.high_risk', { id: brief.id, module: 'M3', score: 0.9 }));
    await waitFor(() => expect(n.list).toBe(2));
    expect(result.current.rt.alerts).toEqual([]);
  });

  it('a held alert stays past its time and restarts the full time when released', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => result.current.hold(uid(1)));
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.alerts).toHaveLength(1);
    act(() => result.current.release(uid(1)));
    act(() => vi.advanceTimersByTime(19_999));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts).toEqual([]);
  });
});
