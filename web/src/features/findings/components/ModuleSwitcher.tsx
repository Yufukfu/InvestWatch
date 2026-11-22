import { useEffect, useRef } from 'react';
import type { ModuleOption } from '../model';
import { MODULE_LABEL, RISK_LABEL } from './labels';

type Props = {
  options: ModuleOption[];
  currentId: string;
  onSelect: (id: string) => void;
  // Set right after a switch: the panel remounts per finding, and keyboard users keep their place.
  autoFocus?: boolean;
};

// The modules that found something in the same material. Shown only when there is more than one.
export function ModuleSwitcher({ options, currentId, onSelect, autoFocus = false }: Props) {
  const currentRef = useRef<HTMLButtonElement>(null);
  const focused = useRef(false);
  const shown = options.length > 1;
  // Once, when the buttons first exist: the sibling list may arrive after the panel mounted.
  useEffect(() => {
    if (!autoFocus || !shown || focused.current) return;
    focused.current = true;
    // After the panel's own open effect, which focuses `Zamknij` in the same commit.
    queueMicrotask(() => currentRef.current?.focus());
  }, [autoFocus, shown]);

  if (!shown) return null;
  return (
    <nav className="module-switch" aria-label="Moduły tego materiału">
      <ul>
        {options.map((o) => {
          const current = o.id === currentId;
          return (
            <li key={o.id}>
              <button
                ref={current ? currentRef : undefined}
                type="button"
                className="module-switch-btn"
                aria-current={current ? 'true' : undefined}
                title={MODULE_LABEL[o.module]}
                onClick={() => !current && onSelect(o.id)}
              >
                <span className="module-switch-module">{o.module}</span>
                {' · '}
                <span className={`risk risk-${o.riskLevel ?? 'none'}`}>{o.riskLevel ? RISK_LABEL[o.riskLevel] : 'Brak danych'}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
