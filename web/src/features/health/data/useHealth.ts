import { useGetHealthQuery } from '../../../api/generated';
import type { HealthState } from '../model';

const POLL_MS = 30_000;

// "unreachable" = no answer from the API; "down" = the API answered that the system is down.
export function useHealth(): { state: HealthState } {
  const { data, isError, isLoading } = useGetHealthQuery(undefined, { pollingInterval: POLL_MS });
  const state: HealthState = isLoading ? 'loading' : isError ? 'unreachable' : (data?.status ?? 'unreachable');
  return { state };
}
