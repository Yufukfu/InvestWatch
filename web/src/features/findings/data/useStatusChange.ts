import { usePatchFindingsByIdMutation } from '../../../api/generated';
import type { FindingStatus } from '../model';

export type StatusPatch = { status?: FindingStatus; note?: string | null };

export type StatusChangeState = {
  save: (patch: StatusPatch) => void;
  isSaving: boolean;
  saved: boolean;
  error: string | undefined;
};

// The API's own message when it sends one (`{ error }`), otherwise a generic Polish one.
function errorText(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const data = 'data' in error ? (error as { data?: unknown }).data : undefined;
    if (typeof data === 'object' && data !== null && 'error' in data && typeof data.error === 'string') return data.error;
    if ('status' in error && error.status === 'FETCH_ERROR') return 'brak połączenia z serwerem';
  }
  return 'nieznany błąd';
}

// Not optimistic: the status on screen changes only after the API answers (web-dashboard rules).
export function useStatusChange(id: string): StatusChangeState {
  const [patch, { isLoading, isSuccess, isError, error }] = usePatchFindingsByIdMutation();
  return {
    save: (body) => void patch({ id, body }),
    isSaving: isLoading,
    saved: isSuccess,
    error: isError ? errorText(error) : undefined,
  };
}
