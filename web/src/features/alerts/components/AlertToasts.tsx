import type { AlertItem } from '../model';

type Props = {
  alerts: AlertItem[];
  onOpen: (id: string) => void;
  onDismiss: (id: string) => void;
  onHold?: (id: string) => void;
  onRelease?: (id: string) => void;
};

// The newest alert is announced through a polite live line (label and title only, not the buttons);
// nothing takes focus. A toast holds while hovered or focused. Titles are scraped content: text only.
export function AlertToasts({ alerts, onOpen, onDismiss, onHold, onRelease }: Props) {
  const newest = alerts[0];
  return (
    <section className="toasts" aria-label="Alerty">
      <p className="sr-label" aria-live="polite">
        {newest ? `Wysokie ryzyko: ${newest.title}` : ''}
      </p>
      {alerts.map((a) => {
        const score = a.score === undefined ? undefined : `wynik ${a.score.toFixed(2)}`;
        const meta = [a.module, score].filter(Boolean).join(' · ');
        return (
          <div
            key={a.id}
            className="toast"
            role="group"
            aria-label={`Wysokie ryzyko: ${a.title}`}
            onMouseEnter={() => onHold?.(a.id)}
            onMouseLeave={() => onRelease?.(a.id)}
            onFocus={() => onHold?.(a.id)}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onRelease?.(a.id);
            }}
          >
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
