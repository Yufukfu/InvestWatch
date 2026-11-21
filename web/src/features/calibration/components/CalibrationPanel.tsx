import { useId } from 'react';
import { formatPercent, formatThreshold } from '../format';
import { CALIBRATION_MODULES, type CalibrationModule, type CalibrationPoint, type CalibrationView } from '../model';
import { CalibrationChart } from './CalibrationChart';

export type CalibrationPanelProps = {
  module: CalibrationModule;
  onModule: (m: CalibrationModule) => void;
  view: CalibrationView | undefined;
  isLoading: boolean;
  isError: boolean;
  /** The thresholds (GET /settings/thresholds) could not be read, so saving is off. */
  settingsError?: boolean;
  index: number;
  currentIndex: number;
  onIndex: (i: number) => void;
  canSave: boolean;
  onSave: (threshold: number) => void;
  isSaving: boolean;
  saved: boolean;
  error: string | undefined;
  chartSize?: { width: number; height: number };
};

const MODULE_NAME: Record<CalibrationModule, string> = {
  M1: 'Finfluencerzy',
  M2: 'Zgodność reklam',
  M3: 'Usługi bez zezwolenia',
};

type Metric = { label: string; value: (p: CalibrationPoint) => number | undefined; percent?: boolean };

// Values are shown exactly as GET /calibration returns them; nothing is recalculated here.
const METRICS: Metric[] = [
  { label: 'Wykryte naruszenia (TP)', value: (p) => p.tp },
  { label: 'Fałszywe alarmy (FP)', value: (p) => p.fp },
  { label: 'Przeoczone (FN)', value: (p) => p.fn },
  { label: 'Poprawnie pominięte (TN)', value: (p) => p.tn },
  { label: 'Precyzja', value: (p) => p.precision, percent: true },
  { label: 'Czułość', value: (p) => p.recall, percent: true },
  { label: 'F1', value: (p) => p.f1, percent: true },
];

const show = (v: number, percent?: boolean) => (percent ? formatPercent(v) : String(v));

const SAVED_TEXT = 'Zapisano. Poziomy ryzyka zostały przeliczone.';

export function CalibrationPanel(props: CalibrationPanelProps) {
  const { module, onModule, view, isLoading, isError, isSaving, settingsError } = props;
  const id = useId();

  let body;
  if (isError) body = <p role="alert">Nie udało się pobrać kalibracji.</p>;
  else if (isLoading || !view) body = <p className="muted" role="status">Ładowanie kalibracji…</p>;
  else if (view.labeledSamples === 0 || view.points.length === 0 || props.index < 0)
    body = <p className="state state-empty">Za mało oznaczonych danych, aby skalibrować ten moduł.</p>;
  else body = <Body {...props} view={view} sliderId={`${id}-slider`} />;

  return (
    <section className="panel calibration" aria-labelledby={`${id}-title`}>
      <div className="panel-header">
        <h2 id={`${id}-title`}>Kalibracja progów</h2>
        <div className="segmented" role="group" aria-label="Moduł">
          {CALIBRATION_MODULES.map((m) => (
            // aria-disabled, not disabled: a disabled button drops keyboard focus to <body>. A module switch
            // would also drop the save feedback while the PUT is still in flight, so it waits for the save.
            <button
              key={m}
              type="button"
              aria-pressed={m === module}
              aria-disabled={isSaving}
              onClick={() => {
                if (!isSaving) onModule(m);
              }}
            >
              {m} · {MODULE_NAME[m]}
            </button>
          ))}
        </div>
      </div>
      {settingsError && <p role="alert">Nie udało się pobrać progów; zapis jest niedostępny.</p>}
      {body}
    </section>
  );
}

function Body({
  module,
  view,
  index,
  currentIndex,
  onIndex,
  canSave,
  onSave,
  isSaving,
  saved,
  error,
  chartSize,
  sliderId,
}: CalibrationPanelProps & { view: CalibrationView; sliderId: string }) {
  const selected = view.points[index];
  const current = view.points[currentIndex] ?? selected;
  // Changed means the user moved off the current point; a saved threshold off the curve is compared
  // with its nearest point, and the comparison says so.
  const changed = index !== currentIndex;
  const exact = current.threshold === view.currentThreshold;
  const beforeLabel = exact ? 'obecnie' : `najbliższy punkt (${formatThreshold(current.threshold)})`;
  const warningId = `${sliderId}-warning`;

  return (
    <>
      <p className="muted">
        Liczba oznaczonych próbek: {view.labeledSamples} (decyzje analityków i zbiór wzorcowy). Przesuń suwak, aby zobaczyć skutki progu;
        podgląd niczego nie zmienia.
      </p>
      <div className="threshold-row">
        <label htmlFor={sliderId}>Próg dla {module}</label>
        <input
          id={sliderId}
          type="range"
          min={0}
          max={view.points.length - 1}
          step={1}
          value={index}
          aria-valuetext={`próg ${formatThreshold(selected.threshold)}`}
          onChange={(e) => onIndex(Number(e.target.value))}
        />
        <span className="threshold-selected">{formatThreshold(selected.threshold)}</span>
        <span className="muted">obecny próg: {formatThreshold(view.currentThreshold)}</span>
      </div>

      <div className="metrics">
        {METRICS.map((m) => {
          const v = m.value(selected);
          if (v === undefined) return null;
          const before = m.value(current);
          return (
            <div key={m.label} className="metric" role="group" aria-label={m.label}>
              <div className="metric-label">{m.label}</div>
              <div className="metric-value">{show(v, m.percent)}</div>
              {before !== undefined && (
                <div className="metric-before">
                  {beforeLabel} {show(before, m.percent)}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <CalibrationChart points={view.points} current={view.currentThreshold} selected={selected.threshold} size={chartSize} />
      <details className="trend-table">
        <summary>Pokaż dane w tabeli</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Próg</th>
              <th scope="col">Precyzja</th>
              <th scope="col">Czułość</th>
              <th scope="col">FP</th>
              <th scope="col">FN</th>
            </tr>
          </thead>
          <tbody>
            {view.points.map((p) => (
              <tr key={p.threshold}>
                <th scope="row">{formatThreshold(p.threshold)}</th>
                <td>{formatPercent(p.precision)}</td>
                <td>{formatPercent(p.recall)}</td>
                <td>{p.fp}</td>
                <td>{p.fn}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <div className="calibration-save">
        <p className="warning" id={warningId}>
          Zapisanie progu zmienia poziom ryzyka wszystkich zgłoszeń modułu {module} i próg alertów wysokiego ryzyka.
        </p>
        <div className="status-actions">
          <button
            type="button"
            className="btn btn-primary"
            // aria-disabled, not disabled: a disabled button drops keyboard focus to <body>.
            aria-disabled={!changed || !canSave || isSaving}
            aria-describedby={warningId}
            onClick={() => {
              if (changed && canSave && !isSaving) onSave(selected.threshold);
            }}
          >
            {isSaving ? 'Zapisywanie…' : 'Zapisz próg'}
          </button>
          {/* Always rendered: removing the focused button would drop focus to <body>. */}
          <button
            type="button"
            className="btn"
            aria-disabled={!changed}
            onClick={() => {
              if (changed) onIndex(currentIndex);
            }}
          >
            Wróć do obecnego
          </button>
          {error && <p role="alert">{error}</p>}
          {/* Always rendered: a live region must exist before its text changes to be announced. */}
          <p role="status" className="saved">
            {saved && !error && !changed ? SAVED_TEXT : ''}
          </p>
        </div>
      </div>
    </>
  );
}
