import { useGetHealthQuery } from '../../api/generated';

export function HealthBadge() {
  const { data, isError, isLoading } = useGetHealthQuery(undefined, { pollingInterval: 30_000 });
  // "unreachable" = no answer from the API; "down" = the API answered that the system is down.
  const state = isLoading ? 'loading' : isError ? 'unreachable' : (data?.status ?? 'unreachable');
  const label =
    {
      loading: 'Sprawdzanie…',
      ok: 'System działa',
      degraded: 'Częściowa awaria',
      down: 'System nie działa',
      unreachable: 'Brak połączenia z API',
    }[state] ?? state;
  return (
    <span className={`badge badge-${state}`} role="status">
      {label}
    </span>
  );
}
