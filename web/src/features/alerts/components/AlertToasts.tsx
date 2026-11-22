import { useEffect, useRef } from 'react';
import { formatScore } from '../../../format/score';
import type { AlertItem } from '../model';

type Props = {
  alerts: AlertItem[];
  // The polite live text, set by the hook when an alert arrives. Dismissing or opening never changes it.
  announcement: string;
  onOpen: (id: string) => void;
  onDismiss: (id: string) => void;
  onHold: (id: string) => void;
  onRelease: (id: string) => void;
};

type Reason = 'pointer' | 'focus';

// Nothing takes focus on arrival. A toast holds while the pointer is over it or keyboard focus is in it;
// the two are tracked separately, so leaving one does not release a toast the other still holds.
// When a toast goes by a button, focus moves first to the next toast (or the region), so it is not lost.
// Titles are scraped content: text only.
export function AlertToasts({ alerts, announcement, onOpen, onDismiss, onHold, onRelease }: Props) {
  const region = useRef<HTMLElement>(null);
  const reasons = useRef(new Map<string, Set<Reason>>());

  // The toasts move when the detail dialog opens or closes. An unmounted toast gets no pointer-leave or
  // blur, so the holds it still has are released here, or they would never end.
  useEffect(() => {
    const held = reasons.current;
    return () => {
      for (const id of held.keys()) onRelease(id);
      held.clear();
    };
  }, [onRelease]);

  // A toast that went (dismissed, opened, pushed out by the cap) gets no pointer-leave or blur either:
  // drop its reasons, so it holds again if the same id comes back. The hook forgets its own hold.
  useEffect(() => {
    const shown = new Set(alerts.map((a) => a.id));
    for (const id of reasons.current.keys()) if (!shown.has(id)) reasons.current.delete(id);
  }, [alerts]);

  const setReason = (id: string, reason: Reason, on: boolean) => {
    const set = reasons.current.get(id) ?? new Set<Reason>();
    const was = set.size > 0;
    if (on) set.add(reason);
    else set.delete(reason);
    if (set.size > 0) reasons.current.set(id, set);
    else reasons.current.delete(id);
    if (!was && set.size > 0) onHold(id);
    if (was && set.size === 0) onRelease(id);
  };

  const focusNeighbour = (id: string) => {
    const ids = alerts.map((a) => a.id);
    const i = ids.indexOf(id);
    const next = ids[i + 1] ?? ids[i - 1];
    const toasts = Array.from(region.current?.querySelectorAll<HTMLElement>('.toast') ?? []);
    const target = toasts.find((el) => el.dataset.id === next)?.querySelector<HTMLElement>('.btn-primary');
    (target ?? region.current)?.focus();
  };

  return (
    <section ref={region} className="toasts" aria-label="Alerty" tabIndex={-1}>
      <p className="sr-label" aria-live="polite">
        {announcement}
      </p>
      {alerts.map((a) => {
        const score = a.score === undefined ? undefined : `wynik ${formatScore(a.score)}`;
        const meta = [a.module, score].filter(Boolean).join(' · ');
        return (
          <div
            key={a.id}
            className="toast"
            data-id={a.id}
            role="group"
            aria-label={`Wysokie ryzyko: ${a.title}`}
            onMouseEnter={() => setReason(a.id, 'pointer', true)}
            onMouseLeave={() => setReason(a.id, 'pointer', false)}
            onFocus={() => setReason(a.id, 'focus', true)}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setReason(a.id, 'focus', false);
            }}
          >
            <p className="toast-head">
              <span className="risk risk-high">Wysokie ryzyko</span>
              {meta && <span className="toast-meta">{meta}</span>}
            </p>
            <p className="toast-title" dir="auto">
              {a.title}
            </p>
            <div className="toast-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  focusNeighbour(a.id);
                  onOpen(a.id);
                }}
              >
                Pokaż
              </button>
              <button
                type="button"
                className="btn"
                aria-label={`Zamknij: ${a.title}`}
                onClick={() => {
                  focusNeighbour(a.id);
                  onDismiss(a.id);
                }}
              >
                Zamknij
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
