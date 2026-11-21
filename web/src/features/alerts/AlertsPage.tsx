import { createPortal } from 'react-dom';
import { useAlertSlot } from '../../alertSlot';
import { AlertToasts } from './components/AlertToasts';
import { LiveBadge } from './components/LiveBadge';
import { useRealtime } from './data/useRealtime';

// Mounted once (in the header): owns the app's only Socket.IO connection.
// The toasts are drawn in the header, or inside the detail dialog while it is open (see toastSlot).
export function AlertsPage() {
  const { connection, alerts, announcement, dismiss, open, hold, release } = useRealtime();
  const { node } = useAlertSlot();
  const toasts = (
    <AlertToasts
      alerts={alerts}
      announcement={announcement}
      onOpen={open}
      onDismiss={dismiss}
      onHold={hold}
      onRelease={release}
    />
  );
  return (
    <>
      <LiveBadge connection={connection} />
      {node ? createPortal(toasts, node) : toasts}
    </>
  );
}
