import { createPortal } from 'react-dom';
import { useAlertSlot } from '../../alertSlot';
import { AlertToasts } from './components/AlertToasts';
import { ConnectionBanner } from './components/ConnectionBanner';
import { LiveBadge } from './components/LiveBadge';
import { useRealtime } from './data/useRealtime';

// Mounted once (in the header): owns the app's only Socket.IO connection.
// The connection-lost banner is drawn in `bannerNode` (a slot above the page content), or in place without one.
// The toasts are drawn in the header, or inside the detail dialog while it is open (see toastSlot).
export function AlertsPage({ bannerNode }: { bannerNode?: HTMLElement | null }) {
  const { connection, alerts, announcement, dismiss, open, hold, release, reconnect } = useRealtime();
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
  const banner = <ConnectionBanner connection={connection} onRetry={reconnect} />;
  return (
    <>
      <LiveBadge connection={connection} />
      {bannerNode ? createPortal(banner, bannerNode) : banner}
      {node ? createPortal(toasts, node) : toasts}
    </>
  );
}
