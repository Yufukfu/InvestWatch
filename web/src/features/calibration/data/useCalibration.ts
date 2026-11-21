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
  canSave: boolean;
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
  const { data } = useGetSettingsThresholdsQuery();
  const [put, { isLoading, isSuccess, isError, error, reset }] = usePutSettingsThresholdsMutation();
  const status = typeof error === 'object' && error !== null && 'status' in error ? error.status : undefined;
  return {
    thresholds: data,
    canSave: data !== undefined,
    save: (module, value) => {
      if (data) void put({ thresholds: { ...data, [module]: value } });
    },
    isSaving: isLoading,
    saved: isSuccess,
    error: isError
      ? `Nie zapisano progu: ${status === 'FETCH_ERROR' ? 'brak połączenia z serwerem.' : status === 422 || status === 400 ? 'serwer odrzucił wartość.' : 'błąd serwera.'}`
      : undefined,
    reset,
  };
}
