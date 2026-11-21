import { useState } from 'react';
import { CalibrationPanel } from './components/CalibrationPanel';
import { useCalibration, useThresholds } from './data/useCalibration';
import { nearestIndex, type CalibrationModule } from './model';

type Props = { chartSize?: { width: number; height: number } };

// The slider's choice, kept only for the module and the saved threshold it was made for.
type Picked = { module: CalibrationModule; base: number | undefined; threshold: number };

export function CalibrationPage({ chartSize }: Props) {
  const [module, setModule] = useState<CalibrationModule>('M2');
  const [picked, setPicked] = useState<Picked | undefined>(undefined);
  const { view, isLoading, isError } = useCalibration(module);
  const thresholds = useThresholds();
  const points = view?.points ?? [];
  const base = view?.currentThreshold;
  const currentIndex = view ? nearestIndex(points, view.currentThreshold) : -1;
  // The selection is a threshold, not a position: a refetched curve with other points keeps it,
  // or falls back to the current point when that threshold is gone. After a save (base changes) or
  // a module switch the old choice is ignored, so the slider starts again at the current point.
  const pickedThreshold = picked && picked.module === module && picked.base === base ? picked.threshold : undefined;
  const at = pickedThreshold === undefined ? -1 : points.findIndex((p) => p.threshold === pickedThreshold);
  const index = at >= 0 ? at : currentIndex;
  return (
    <CalibrationPanel
      module={module}
      onModule={(m) => {
        // The panel does not offer a switch while a save is in flight, so a reset never drops a pending save.
        thresholds.reset();
        setPicked(undefined);
        setModule(m);
      }}
      view={view}
      isLoading={isLoading}
      isError={isError}
      settingsError={thresholds.settingsError}
      index={index}
      currentIndex={currentIndex}
      onIndex={(i) => {
        const threshold = points[i]?.threshold;
        if (threshold !== undefined) setPicked({ module, base, threshold });
      }}
      canSave={thresholds.canSave}
      onSave={(t) => thresholds.save(module, t)}
      isSaving={thresholds.isSaving}
      saved={thresholds.saved}
      error={thresholds.error}
      chartSize={chartSize}
    />
  );
}
