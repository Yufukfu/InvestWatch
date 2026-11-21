export type HealthState = 'loading' | 'ok' | 'degraded' | 'down' | 'unreachable';

const LABEL: Record<HealthState, string> = {
  loading: 'Sprawdzanie…',
  ok: 'System działa',
  degraded: 'Częściowa awaria',
  down: 'System nie działa',
  unreachable: 'Brak połączenia z API',
};

export function HealthBadge({ state }: { state: HealthState }) {
  return (
    <span className={`badge badge-${state}`} role="status">
      {LABEL[state]}
    </span>
  );
}
