import { useGetHealthQuery } from '../../api/generated';

export function HealthBadge() {
  const { data, isError, isLoading } = useGetHealthQuery(undefined, { pollingInterval: 30_000 });
  const state = isLoading ? 'loading' : isError ? 'down' : (data?.status ?? 'down');
  const label = { loading: 'Sprawdzanie…', ok: 'System działa', degraded: 'Częściowa awaria', down: 'Brak połączenia z API' }[state] ?? state;
  return (
    <span className={`badge badge-${state}`} role="status">
      {label}
    </span>
  );
}
