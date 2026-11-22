import type { Connection } from '../model';

// Components sheet: amber banner shown while the live connection is down (the data itself still loads over REST).
export function ConnectionBanner({ connection, onRetry }: { connection: Connection; onRetry: () => void }) {
  if (connection !== 'offline') return null;
  return (
    <div className="connection-banner" role="status">
      <p>Brak połączenia na żywo. Alerty mogą się opóźniać; dane odświeżą się po ponownym połączeniu.</p>
      <button type="button" className="btn btn-ghost" onClick={onRetry}>
        Spróbuj ponownie
      </button>
    </div>
  );
}
