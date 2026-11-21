import { AlertToasts } from './components/AlertToasts';
import { LiveBadge } from './components/LiveBadge';
import { useRealtime } from './data/useRealtime';

// Mounted once (in the header): owns the app's only Socket.IO connection.
export function AlertsPage() {
  const { connection, alerts, dismiss, open, hold, release } = useRealtime();
  return (
    <>
      <LiveBadge connection={connection} />
      <AlertToasts alerts={alerts} onOpen={open} onDismiss={dismiss} onHold={hold} onRelease={release} />
    </>
  );
}
