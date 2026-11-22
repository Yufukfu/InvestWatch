import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import type { ThunkDispatch, UnknownAction } from '@reduxjs/toolkit';
import { investWatchApi, type GetFindingsApiArg } from '../../../api/generated';
import { isolate } from '../../../format/bidi';
import { setSearchParam } from '../../../url/useUrlSearch';
import { isUuid } from '../../../url/uuid';
import type { AlertItem, Connection } from '../model';
import { connectEvents } from './socket';

const STATUSES = ['new', 'in_review', 'confirmed', 'false_positive', 'closed'] as const;
type Status = (typeof STATUSES)[number];
const MODULES = ['M1', 'M2', 'M3'] as const;

export const MAX_ALERTS = 4;
export const ALERT_TTL_MS = 20_000;
// A burst of created or high-risk events refetches the lists once, after the burst.
export const REFRESH_DEBOUNCE_MS = 1_000;
export const MAX_TITLE_LENGTH = 200;

type State = ReturnType<typeof investWatchApi.reducer>;
type Dispatch = ThunkDispatch<{ [investWatchApi.reducerPath]: State }, unknown, UnknownAction>;

function record(v: unknown): Record<string, unknown> | undefined {
  return typeof v === 'object' && v !== null ? (v as Record<string, unknown>) : undefined;
}

// Event payloads come from the network: check the fields we use, ignore the rest. `id` is checked by the caller.
function toAlert(id: string, p: Record<string, unknown>): AlertItem | undefined {
  if (typeof p.title !== 'string') return undefined;
  const title = Array.from(p.title.trim()).slice(0, MAX_TITLE_LENGTH).join('');
  if (title === '') return undefined;
  return {
    id,
    title,
    module: (MODULES as readonly unknown[]).includes(p.module) ? (p.module as AlertItem['module']) : undefined,
    score: typeof p.score === 'number' ? p.score : undefined,
  };
}

export type RealtimeState = {
  connection: Connection;
  alerts: AlertItem[];
  // The polite live text: set when a high-risk alert arrives, unchanged by dismiss or open.
  announcement: string;
  dismiss: (id: string) => void;
  open: (id: string) => void;
  hold: (id: string) => void;
  release: (id: string) => void;
};

// The single real-time subscription of the app (web-dashboard rules): finding.created/high_risk
// invalidate, finding.updated patches the cache, high_risk also raises a toast.
export function useRealtime(): RealtimeState {
  const dispatch = useDispatch<Dispatch>();
  const [connection, setConnection] = useState<Connection>('connecting');
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [announcement, setAnnouncement] = useState('');
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const held = useRef(new Set<string>());

  const dismiss = useCallback((id: string) => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    held.current.delete(id);
    setAlerts((list) => list.filter((a) => a.id !== id));
  }, []);

  const schedule = useCallback(
    (id: string) => {
      clearTimeout(timers.current.get(id));
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), ALERT_TTL_MS),
      );
    },
    [dismiss],
  );

  // A toast under the pointer or holding focus stays until released (WCAG 2.2.1, focus never lost).
  const hold = useCallback((id: string) => {
    held.current.add(id);
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);
  const release = useCallback(
    (id: string) => {
      held.current.delete(id);
      schedule(id);
    },
    [schedule],
  );

  // A toast pushed out by the cap unmounts without a pointer-leave or blur: forget its hold and timer,
  // or it would stay held, and never time out, when the same id arrives again. The socket handler can
  // run between that render and this effect and see the stale hold, so every shown toast that is
  // neither held nor timed gets its timer here: each shown toast is always one or the other.
  useEffect(() => {
    const shown = new Set(alerts.map((a) => a.id));
    for (const id of held.current) if (!shown.has(id)) held.current.delete(id);
    for (const [id, timer] of timers.current) {
      if (!shown.has(id)) {
        clearTimeout(timer);
        timers.current.delete(id);
      }
    }
    for (const id of shown) if (!held.current.has(id) && !timers.current.has(id)) schedule(id);
  }, [alerts, schedule]);

  const open = useCallback(
    (id: string) => {
      setSearchParam('finding', id);
      dismiss(id);
    },
    [dismiss],
  );

  useEffect(() => {
    const live = timers.current;
    const heldIds = held.current;
    const socket = connectEvents();
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => dispatch(investWatchApi.util.invalidateTags(['findings', 'stats']));
    const refreshSoon = () => {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(refresh, REFRESH_DEBOUNCE_MS);
    };

    const onCreated = (payload: unknown) => {
      if (isUuid(record(payload)?.id)) refreshSoon();
    };
    const onHighRisk = (payload: unknown) => {
      const p = record(payload);
      if (!p || !isUuid(p.id)) return;
      refreshSoon();
      const alert = toAlert(p.id, p);
      if (!alert) return;
      if (!held.current.has(alert.id)) schedule(alert.id);
      setAlerts((list) => [alert, ...list.filter((a) => a.id !== alert.id)].slice(0, MAX_ALERTS));
      setAnnouncement(`Wysokie ryzyko: ${isolate(alert.title)}`);
    };
    const onUpdated = (payload: unknown) => {
      const p = record(payload);
      if (!p || !isUuid(p.id) || !(STATUSES as readonly unknown[]).includes(p.status)) return;
      const id = p.id;
      const status = p.status as Status;
      dispatch((d: Dispatch, getState: () => { [investWatchApi.reducerPath]: State }) => {
        let filtered = false;
        for (const args of investWatchApi.util.selectCachedArgsForQuery(getState(), 'getFindings')) {
          // A row can leave a status filter: that list is refetched, not patched.
          if ((args as GetFindingsApiArg | undefined)?.status) filtered = true;
          d(
            investWatchApi.util.updateQueryData('getFindings', args, (draft) => {
              const row = draft.items.find((i) => i.id === id);
              if (row) row.status = status;
            }),
          );
        }
        d(
          investWatchApi.util.updateQueryData('getFindingsById', { id }, (draft) => {
            draft.status = status;
          }),
        );
        // Counts move, and analyst labels feed the calibration curve.
        d(investWatchApi.util.invalidateTags(filtered ? ['findings', 'stats', 'calibration'] : ['stats', 'calibration']));
      });
    };

    socket.on('connect', () => {
      setConnection('live');
      // Pub/Sub has no replay: whatever happened while disconnected is fetched over REST, at once.
      clearTimeout(refreshTimer);
      refresh();
    });
    socket.on('disconnect', () => setConnection('offline'));
    socket.on('connect_error', () => setConnection('offline'));
    socket.on('finding.created', onCreated);
    socket.on('finding.high_risk', onHighRisk);
    socket.on('finding.updated', onUpdated);

    return () => {
      socket.disconnect();
      clearTimeout(refreshTimer);
      live.forEach(clearTimeout);
      live.clear();
      heldIds.clear();
    };
  }, [dispatch, schedule]);

  return { connection, alerts, announcement, dismiss, open, hold, release };
}
