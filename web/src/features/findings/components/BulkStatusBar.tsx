import type { BulkOutcome, FindingStatus } from '../model';
import { findingsCount, STATUS_LABEL } from './labels';

// The mockup's verbs, in its order; `Nowe` puts a finding back in the queue.
const ACTIONS: ReadonlyArray<[FindingStatus, string]> = [
  ['confirmed', 'Potwierdź'],
  ['in_review', 'W analizie'],
  ['false_positive', 'Fałszywy alarm'],
  ['closed', 'Zamknij'],
  ['new', 'Nowe'],
];

const RESULT_LABEL: Record<BulkOutcome['items'][number]['result'], string> = {
  updated: 'zaktualizowano',
  not_found: 'nie znaleziono',
};

type Props = {
  count: number;
  onApply: (status: FindingStatus) => void;
  onClear: () => void;
  isSaving: boolean;
  error: { message: string; detail: string | undefined } | undefined;
  outcome: BulkOutcome | undefined;
  onDismiss: () => void;
};

// "Masowe działania": the bar while findings are selected, then the per-item result of the last change.
// Titles are untrusted: plain text, each in its own dir="auto" element.
export function BulkStatusBar({ count, onApply, onClear, isSaving, error, outcome, onDismiss }: Props) {
  return (
    <>
      {count > 0 && (
        <section className="bulk-bar" aria-label="Masowe działania">
          <p className="bulk-count">
            <strong>Zaznaczono {findingsCount(count)}</strong> <span className="bulk-hint">Esc — wyczyść zaznaczenie</span>
          </p>
          <div className="bulk-actions" role="group" aria-label="Ustaw status zaznaczonych">
            {ACTIONS.map(([status, label], i) => (
              <button
                key={status}
                type="button"
                className={i === 0 ? 'btn bulk-btn bulk-btn-primary' : 'btn bulk-btn'}
                aria-disabled={isSaving || undefined}
                onClick={() => {
                  if (!isSaving) onApply(status);
                }}
              >
                {label}
              </button>
            ))}
            <button type="button" className="btn bulk-btn bulk-btn-ghost" onClick={onClear}>
              Wyczyść zaznaczenie
            </button>
          </div>
          {error && (
            <p className="bulk-error" role="alert">
              Nie udało się zmienić statusu: {error.message}
              {error.detail && (
                <>
                  {' '}
                  <span dir="auto">({error.detail})</span>
                </>
              )}
            </p>
          )}
        </section>
      )}
      {outcome && (
        <section className="bulk-result" role="status" aria-label="Wynik zmiany statusu">
          <p className="bulk-result-summary">
            Nowy status: {STATUS_LABEL[outcome.status]}. Zaktualizowano: {outcome.updated}. Nie znaleziono: {outcome.notFound}.
          </p>
          <ul className="bulk-result-list">
            {outcome.items.map((item) => (
              <li key={item.id} className={`bulk-item bulk-item-${item.result}`}>
                <span dir="auto">{item.title}</span> — {RESULT_LABEL[item.result]}
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-ghost" onClick={onDismiss}>
            Ukryj wynik
          </button>
        </section>
      )}
    </>
  );
}
