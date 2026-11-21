import type { AlertItem } from '../model';

type Props = { alerts: AlertItem[]; onOpen: (id: string) => void; onDismiss: (id: string) => void };

// Polite live region: announced by screen readers without moving focus. The region is always in the
// DOM, so additions are announced. Titles come from scraped content and are rendered as text.
export function AlertToasts({ alerts, onOpen, onDismiss }: Props) {
  return (
    <section className="toasts" aria-label="Alerty" aria-live="polite">
      {alerts.map((a) => {
        const score = a.score === undefined ? undefined : `wynik ${a.score.toFixed(2)}`;
        const meta = [a.module, score].filter(Boolean).join(' · ');
        return (
          <div key={a.id} className="toast" role="group" aria-label={`Wysokie ryzyko: ${a.title}`}>
            <p className="toast-head">
              <span className="risk risk-high">Wysokie ryzyko</span>
              {meta && <span className="toast-meta">{meta}</span>}
            </p>
            <p className="toast-title">{a.title}</p>
            <div className="toast-actions">
              <button type="button" className="btn btn-primary" onClick={() => onOpen(a.id)}>
                Pokaż
              </button>
              <button type="button" className="btn" aria-label="Zamknij alert" onClick={() => onDismiss(a.id)}>
                Zamknij
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
