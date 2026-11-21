import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGetCalibrationQuery, useGetFindingsByIdQuery, useGetFindingsQuery, useGetStatsSummaryQuery } from '../../../api/generated';
import detail from '../../../test/fixtures/finding-detail.json';
import findings from '../../../test/fixtures/findings.json';
import summary from '../../../test/fixtures/summary.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useRealtime } from './useRealtime';

// The debounced refresh (1 s) is waited for with this timeout.
const SLOW = { timeout: 3000 };

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
  const n = { list: 0, summary: 0, calibration: 0 };
  server.use(
    http.get('http://localhost/api/calibration', () => {
      n.calibration += 1;
      return HttpResponse.json({ module: 'M2', current_threshold: 0.5, labeled_samples: 0, points: [] });
    }),
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
      calibration: useGetCalibrationQuery({ module: 'M2' }),
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

  it('refetches findings and stats on every connect, at once', async () => {
    const n = countRequests();
    renderWithQueries();
    await waitFor(() => expect(n.list).toBe(1));
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire('connect'));
    await waitFor(() => expect(n.list).toBe(2), { timeout: 500 });
    await waitFor(() => expect(n.summary).toBe(2), { timeout: 500 });
  });

  it.each(['finding.created', 'finding.high_risk'])('%s refetches findings and stats', async (event) => {
    const n = countRequests();
    renderWithQueries();
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire(event, brief));
    await waitFor(() => expect(n.list).toBe(2), SLOW);
    await waitFor(() => expect(n.summary).toBe(2), SLOW);
  });

  it('coalesces a burst of created events into one refetch after the burst', async () => {
    const n = countRequests();
    renderWithQueries();
    await waitFor(() => expect(n.list).toBe(1));
    act(() => {
      for (let i = 0; i < 5; i++) fake.fire('finding.created', { ...brief, id: uid(i) });
    });
    await new Promise((r) => setTimeout(r, 300));
    expect(n.list).toBe(1);
    await waitFor(() => expect(n.list).toBe(2), SLOW);
    await new Promise((r) => setTimeout(r, 1200));
    expect(n.list).toBe(2);
  });

  it('finding.updated patches only the changed row, in every cached list, without refetching', async () => {
    const n = countRequests();
    const { result } = renderHook(
      () => ({
        rt: useRealtime(),
        first: useGetFindingsQuery({ page: 1, pageSize: 25 }),
        second: useGetFindingsQuery({ page: 2, pageSize: 25 }),
        detail: useGetFindingsByIdQuery({ id: detail.id }),
      }),
      { wrapper: storeWrapper() },
    );
    await waitFor(() => expect(result.current.first.data).toBeDefined());
    await waitFor(() => expect(result.current.second.data).toBeDefined());
    const target = findings.items[2];
    const next = target.status === 'closed' ? 'confirmed' : 'closed';
    const before = findings.items.map((i) => i.status);
    const expected = before.map((s, i) => (i === 2 ? next : s));
    act(() => fake.fire('finding.updated', { id: target.id, status: next }));
    await waitFor(() => expect(result.current.first.data?.items[2].status).toBe(next));
    await waitFor(() => expect(result.current.second.data?.items[2].status).toBe(next));
    expect(result.current.first.data?.items.map((i) => i.status)).toEqual(expected);
    expect(result.current.second.data?.items.map((i) => i.status)).toEqual(expected);
    expect(result.current.detail.data?.id).toBe(detail.id);
    expect(n.list).toBe(2);
  });

  it('finding.updated refreshes the stats and the calibration curve, because analyst labels feed it', async () => {
    const n = countRequests();
    const { result } = renderWithQueries();
    await waitFor(() => expect(result.current.calibration.data).toBeDefined());
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire('finding.updated', { id: detail.id, status: 'closed' }));
    await waitFor(() => expect(n.summary).toBe(2));
    await waitFor(() => expect(n.calibration).toBe(2));
  });

  it('finding.updated refetches the list when a status filter is active, because the row may leave it', async () => {
    const n = countRequests();
    const { result } = renderHook(
      () => ({ rt: useRealtime(), filtered: useGetFindingsQuery({ page: 1, pageSize: 25, status: 'new' }) }),
      { wrapper: storeWrapper() },
    );
    await waitFor(() => expect(result.current.filtered.data).toBeDefined());
    expect(n.list).toBe(1);
    act(() => fake.fire('finding.updated', { id: findings.items[2].id, status: 'closed' }));
    await waitFor(() => expect(n.list).toBe(2));
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
    await new Promise((r) => setTimeout(r, 1200));
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

  it('announces the arriving alert; dismissing a newer one leaves the announcement alone', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      fake.fire('finding.high_risk', { ...brief, id: uid(1), title: 'Stary' });
      fake.fire('finding.high_risk', { ...brief, id: uid(2), title: 'Nowy' });
    });
    expect(result.current.announcement).toBe('Wysokie ryzyko: Nowy');
    act(() => result.current.dismiss(uid(2)));
    expect(result.current.announcement).toBe('Wysokie ryzyko: Nowy');
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(1)]);
    act(() => result.current.open(uid(1)));
    expect(result.current.announcement).toBe('Wysokie ryzyko: Nowy');
  });

  it('does not alert on finding.created', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.created', brief));
    expect(result.current.alerts).toEqual([]);
    expect(result.current.announcement).toBe('');
  });

  it('raises no toast for a blank title and cuts a long title to 200 characters', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      fake.fire('finding.high_risk', { ...brief, id: uid(1), title: '' });
      fake.fire('finding.high_risk', { ...brief, id: uid(2), title: '   ' });
    });
    expect(result.current.alerts).toEqual([]);
    expect(result.current.announcement).toBe('');
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(3), title: 'x'.repeat(500) }));
    expect(result.current.alerts[0].title).toHaveLength(200);
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

  it('dismissing the middle of three keeps the others in order', () => {
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      fake.fire('finding.high_risk', { ...brief, id: uid(1) });
      fake.fire('finding.high_risk', { ...brief, id: uid(2) });
      fake.fire('finding.high_risk', { ...brief, id: uid(3) });
    });
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(3), uid(2), uid(1)]);
    act(() => result.current.dismiss(uid(2)));
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(3), uid(1)]);
  });

  it('a repeated event for an alert restarts its timer and does not leave the first one running', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => vi.advanceTimersByTime(15_000));
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => vi.advanceTimersByTime(6_000));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(13_999));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts).toEqual([]);
  });

  it('open() puts the finding in the URL and dismisses only its alert', () => {
    window.history.replaceState(null, '', '/?module=M3');
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => {
      fake.fire('finding.high_risk', { ...brief, id: uid(1) });
      fake.fire('finding.high_risk', { ...brief, id: detail.id });
    });
    act(() => result.current.open(detail.id));
    expect(window.location.search).toBe(`?module=M3&finding=${detail.id}`);
    expect(result.current.alerts.map((a) => a.id)).toEqual([uid(1)]);
  });

  it('a high-risk event without a title still refreshes, but raises no toast', async () => {
    const n = countRequests();
    const { result } = renderWithQueries();
    await waitFor(() => expect(n.summary).toBe(1));
    act(() => fake.fire('finding.high_risk', { id: brief.id, module: 'M3', score: 0.9 }));
    await waitFor(() => expect(n.list).toBe(2), SLOW);
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

  it('a repeated high-risk event for a held toast does not restart its timer', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => result.current.hold(uid(1)));
    act(() => vi.advanceTimersByTime(10_000));
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.alerts).toHaveLength(1);
    act(() => result.current.release(uid(1)));
    act(() => vi.advanceTimersByTime(19_999));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts).toEqual([]);
  });

  it('a held toast pushed out by the 4-toast cap is not held when it arrives again', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => result.current.hold(uid(1)));
    for (let n = 2; n <= 5; n += 1) act(() => fake.fire('finding.high_risk', { ...brief, id: uid(n) }));
    expect(result.current.alerts.map((a) => a.id)).not.toContain(uid(1));
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => vi.advanceTimersByTime(19_999));
    expect(result.current.alerts.map((a) => a.id)).toContain(uid(1));
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts.map((a) => a.id)).not.toContain(uid(1));
  });

  it('a released toast is no longer held: a repeated event restarts its time', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(), { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => result.current.hold(uid(1)));
    act(() => result.current.release(uid(1)));
    act(() => vi.advanceTimersByTime(10_000));
    act(() => fake.fire('finding.high_risk', { ...brief, id: uid(1) }));
    act(() => vi.advanceTimersByTime(19_999));
    expect(result.current.alerts).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.alerts).toEqual([]);
  });
});
