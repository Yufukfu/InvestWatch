import {
  useGetCalibrationQuery,
  useGetSettingsThresholdsQuery,
  usePutSettingsThresholdsMutation,
  type Thresholds,
} from '../../../api/generated';
import type { CalibrationModule, CalibrationView } from '../model';

export function useCalibration(module: CalibrationModule): {
  view: CalibrationView | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  const { currentData, isFetching, isError } = useGetCalibrationQuery({ module });
  return {
    view: currentData
      ? {
          module: currentData.module,
          currentThreshold: currentData.current_threshold,
          labeledSamples: currentData.labeled_samples,
          points: currentData.points,
        }
      : undefined,
    isLoading: isFetching && !currentData,
    isError,
  };
}

export type ThresholdsState = {
  thresholds: Thresholds | undefined;
  /** False until the thresholds are read, and again while a refetch (e.g. after a save) is running. */
  canSave: boolean;
  settingsError: boolean;
  save: (module: CalibrationModule, value: number) => void;
  isSaving: boolean;
  saved: boolean;
  error: string | undefined;
  reset: () => void;
};

// The PUT body is the saved thresholds with one module replaced: the panel never invents the others.
// The PUT is global (recomputes risk_level, changes the alert threshold); src/api/enhanced.ts makes it
// invalidate findings, stats and calibration as well as settings.
export function useThresholds(): ThresholdsState {
  const { data, isFetching, isError: settingsError } = useGetSettingsThresholdsQuery();
  const [put, { isLoading, isSuccess, isError, error, reset }] = usePutSettingsThresholdsMutation();
  const canSave = data !== undefined && !isFetching;
  return {
    thresholds: data,
    canSave,
    settingsError,
    save: (module, value) => {
      // Built from the settled read only: right after a save the cached set is the one before it.
      if (!canSave || isLoading || !data) return;
      void put({ thresholds: { ...data, [module]: value } });
    },
    isSaving: isLoading,
    saved: isSuccess,
    error: isError ? `Nie zapisano progu: ${saveFailure(error)}` : undefined,
    reset,
  };
}

// Says what went wrong without blaming the server for a request it did not receive.
function saveFailure(error: unknown): string {
  const status = typeof error === 'object' && error !== null && 'status' in error ? error.status : undefined;
  if (status === 'FETCH_ERROR') return 'brak połączenia z serwerem.';
  if (status === 400 || status === 422) return 'serwer odrzucił wartość.';
  if (typeof status === 'number' && status >= 400 && status < 500) return 'serwer odrzucił żądanie.';
  return 'błąd serwera.';
}
