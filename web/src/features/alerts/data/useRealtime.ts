import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import type { ThunkDispatch, UnknownAction } from '@reduxjs/toolkit';
import { investWatchApi } from '../../../api/generated';
import { setSearchParam } from '../../../url/useUrlSearch';
import type { AlertItem, Connection } from '../model';
import { connectEvents } from './socket';

const STATUSES = ['new', 'in_review', 'confirmed', 'false_positive', 'closed'] as const;
type Status = (typeof STATUSES)[number];
const MODULES = ['M1', 'M2', 'M3'] as const;

export const MAX_ALERTS = 4;
export const ALERT_TTL_MS = 20_000;

type State = ReturnType<typeof investWatchApi.reducer>;
type Dispatch = ThunkDispatch<{ [investWatchApi.reducerPath]: State }, unknown, UnknownAction>;

function record(v: unknown): Record<string, unknown> | undefined {
  return typeof v === 'object' && v !== null ? (v as Record<string, unknown>) : undefined;
}

// Event payloads come from the network: check the fields we use, ignore the rest.
function toAlert(payload: unknown): AlertItem | undefined {
  const p = record(payload);
  if (!p || typeof p.id !== 'string' || typeof p.title !== 'string') return undefined;
  return {
    id: p.id,
    title: p.title,
    module: (MODULES as readonly unknown[]).includes(p.module) ? (p.module as AlertItem['module']) : undefined,
    score: typeof p.score === 'number' ? p.score : undefined,
  };
}

export type RealtimeState = {
  connection: Connection;
  alerts: AlertItem[];
  dismiss: (id: string) => void;
  open: (id: string) => void;
};

// The single real-time subscription of the app (web-dashboard rules): finding.created/high_risk
// invalidate, finding.updated patches the cache, high_risk also raises a toast.
export function useRealtime(): RealtimeState {
  const dispatch = useDispatch<Dispatch>();
  const [connection, setConnection] = useState<Connection>('connecting');
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setAlerts((list) => list.filter((a) => a.id !== id));
  }, []);

  const open = useCallback(
    (id: string) => {
      setSearchParam('finding', id);
      dismiss(id);
    },
    [dismiss],
  );

  useEffect(() => {
    const live = timers.current;
    const socket = connectEvents();
    const refresh = () => dispatch(investWatchApi.util.invalidateTags(['findings', 'stats']));

    const onCreated = (payload: unknown) => {
      if (typeof record(payload)?.id === 'string') refresh();
    };
    const onHighRisk = (payload: unknown) => {
      const alert = toAlert(payload);
      if (!alert) return;
      refresh();
      clearTimeout(live.get(alert.id));
      live.set(
        alert.id,
        setTimeout(() => {
          live.delete(alert.id);
          setAlerts((list) => list.filter((a) => a.id !== alert.id));
        }, ALERT_TTL_MS),
      );
      setAlerts((list) => [alert, ...list.filter((a) => a.id !== alert.id)].slice(0, MAX_ALERTS));
    };
    const onUpdated = (payload: unknown) => {
      const p = record(payload);
      if (!p || typeof p.id !== 'string' || !(STATUSES as readonly unknown[]).includes(p.status)) return;
      const id = p.id;
      const status = p.status as Status;
      dispatch((d: Dispatch, getState: () => { [investWatchApi.reducerPath]: State }) => {
        for (const args of investWatchApi.util.selectCachedArgsForQuery(getState(), 'getFindings')) {
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
        d(investWatchApi.util.invalidateTags(['stats']));
      });
    };

    socket.on('connect', () => {
      setConnection('live');
      // Pub/Sub has no replay: whatever happened while disconnected is fetched over REST.
      refresh();
    });
    socket.on('disconnect', () => setConnection('offline'));
    socket.on('connect_error', () => setConnection('offline'));
    socket.on('finding.created', onCreated);
    socket.on('finding.high_risk', onHighRisk);
    socket.on('finding.updated', onUpdated);

    return () => {
      socket.disconnect();
      live.forEach(clearTimeout);
      live.clear();
    };
  }, [dispatch]);

  return { connection, alerts, dismiss, open };
}
