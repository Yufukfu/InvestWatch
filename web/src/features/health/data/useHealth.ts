import { useGetHealthQuery } from '../../../api/generated';
import type { HealthState } from '../components/HealthBadge';

const POLL_MS = 30_000;

// "unreachable" = no answer from the API; "down" = the API answered that the system is down.
export function useHealth(pollingInterval: number = POLL_MS): { state: HealthState } {
  const { data, isError, isLoading } = useGetHealthQuery(undefined, { pollingInterval });
  const state: HealthState = isLoading ? 'loading' : isError ? 'unreachable' : (data?.status ?? 'unreachable');
  return { state };
}
