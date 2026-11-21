import { useState, type ReactNode } from 'react';
import { CalibrationPanel } from './components/CalibrationPanel';
import { useCalibration, useThresholds } from './data/useCalibration';
import { nearestIndex, type CalibrationModule } from './model';

type Props = { chartSize?: { width: number; height: number } };

export function CalibrationPage({ chartSize }: Props) {
  const [module, setModule] = useState<CalibrationModule>('M2');
  const { view, isLoading, isError } = useCalibration(module);
  const thresholds = useThresholds();
  const points = view?.points ?? [];
  const currentIndex = view ? nearestIndex(points, view.currentThreshold) : -1;
  // A new module or a saved threshold starts the slider again at the current point.
  const key = `${module}|${view?.currentThreshold ?? ''}`;
  return (
    <Selection key={key}>
      {(picked, pick) => {
        // The selection is a threshold, not a position: a refetched curve with other points keeps it,
        // or falls back to the current point when that threshold is gone.
        const at = picked === undefined ? -1 : points.findIndex((p) => p.threshold === picked);
        const index = at >= 0 ? at : currentIndex;
        return (
          <CalibrationPanel
            module={module}
            onModule={(m) => {
              // Save feedback belongs to the module it was for.
              thresholds.reset();
              setModule(m);
            }}
            view={view}
            isLoading={isLoading}
            isError={isError}
            index={index}
            currentIndex={currentIndex}
            onIndex={(i) => pick(points[i]?.threshold)}
            canSave={thresholds.canSave}
            onSave={(t) => thresholds.save(module, t)}
            isSaving={thresholds.isSaving}
            saved={thresholds.saved}
            error={thresholds.error}
            chartSize={chartSize}
          />
        );
      }}
    </Selection>
  );
}

// Holds the picked threshold; remounted (by key) when the module or the saved threshold changes.
function Selection({ children }: { children: (picked: number | undefined, pick: (t: number | undefined) => void) => ReactNode }) {
  const [picked, setPicked] = useState<number | undefined>(undefined);
  return <>{children(picked, setPicked)}</>;
}
