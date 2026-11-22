import { usePatchFindingsByIdMutation } from '../../../api/generated';
import type { FindingStatus } from '../model';

export type StatusPatch = { status?: FindingStatus; note?: string | null };

export type StatusChangeState = {
  save: (patch: StatusPatch) => void;
  isSaving: boolean;
  saved: boolean;
  error: SaveError | undefined;
};

export type SaveError = { message: string; detail: string | undefined };

const BY_STATUS: Record<number, string> = {
  400: 'serwer odrzucił tę wartość.',
  404: 'zgłoszenie już nie istnieje.',
  409: 'zgłoszenie zmieniło się w międzyczasie, odśwież widok.',
  422: 'serwer odrzucił tę wartość.',
};

// A Polish message chosen by HTTP status; the API's own `{ error }` text is kept as a separate detail
// (it is English), so the alert itself never mixes languages.
export function toSaveError(error: unknown): SaveError {
  const e = (typeof error === 'object' && error !== null ? error : {}) as { status?: unknown; data?: unknown };
  const data = e.data as { error?: unknown } | undefined;
  const detail = typeof data === 'object' && data !== null && typeof data.error === 'string' ? data.error : undefined;
  if (e.status === 'FETCH_ERROR') return { message: 'brak połączenia z serwerem.', detail };
  const message = typeof e.status === 'number' ? (BY_STATUS[e.status] ?? 'błąd serwera, spróbuj ponownie.') : 'nieznany błąd.';
  return { message, detail };
}

// Not optimistic: the status on screen changes only after the API answers (web-dashboard rules).
export function useStatusChange(id: string): StatusChangeState {
  const [patch, { isLoading, isSuccess, isError, error }] = usePatchFindingsByIdMutation();
  return {
    save: (body) => void patch({ id, body }),
    isSaving: isLoading,
    saved: isSuccess,
    error: isError ? toSaveError(error) : undefined,
  };
}
