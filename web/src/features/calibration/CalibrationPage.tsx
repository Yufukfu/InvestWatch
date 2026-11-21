import { useState, type ReactNode } from 'react';
import { CalibrationPanel } from './components/CalibrationPanel';
import { useCalibration, useThresholds } from './data/useCalibration';
import { nearestIndex, type CalibrationModule } from './model';

type Props = { chartSize?: { width: number; height: number } };

export function CalibrationPage({ chartSize }: Props) {
  const [module, setModule] = useState<CalibrationModule>('M2');
  const { view, isLoading, isError } = useCalibration(module);
  const thresholds = useThresholds();
  const currentIndex = view ? nearestIndex(view.points, view.currentThreshold) : -1;
  // A new module or a saved threshold starts the slider again at the current point.
  const key = `${module}|${view?.currentThreshold ?? ''}`;
  return (
    <Selection key={key} currentIndex={currentIndex}>
      {(index, setIndex) => (
        <CalibrationPanel
          module={module}
          onModule={setModule}
          view={view}
          isLoading={isLoading}
          isError={isError}
          index={index}
          currentIndex={currentIndex}
          onIndex={setIndex}
          canSave={thresholds.canSave}
          onSave={(t) => thresholds.save(module, t)}
          isSaving={thresholds.isSaving}
          saved={thresholds.saved}
          error={thresholds.error}
          chartSize={chartSize}
        />
      )}
    </Selection>
  );
}

// Holds the slider position; remounted (by key) when the module or the saved threshold changes.
function Selection({ currentIndex, children }: { currentIndex: number; children: (i: number, set: (i: number) => void) => ReactNode }) {
  const [picked, setPicked] = useState<number | undefined>(undefined);
  return <>{children(picked ?? currentIndex, setPicked)}</>;
}
