import type { Connection } from '../model';

const LABEL: Record<Connection, string> = {
  connecting: 'Łączenie…',
  live: 'Na żywo',
  offline: 'Brak połączenia na żywo',
};

export function LiveBadge({ connection }: { connection: Connection }) {
  return <span className={`live live-${connection}`}>{LABEL[connection]}</span>;
}
