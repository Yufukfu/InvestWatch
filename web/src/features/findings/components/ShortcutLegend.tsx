import { STATUSES } from '../model';
import { STATUS_LABEL } from './labels';

// "1 Nowe · 2 W analizie · …": the status behind each digit, in the order useFindingShortcuts maps them.
const STATUS_KEYS = STATUSES.map((s, i) => `${i + 1} ${STATUS_LABEL[s]}`).join(' · ');

const SHORTCUTS: { action: string; keys: string; hint?: string }[] = [
  { action: 'Następne / poprzednie zgłoszenie', keys: 'J K' },
  { action: 'Zmień status', keys: '1 – 5', hint: STATUS_KEYS },
  { action: 'Otwórz źródło', keys: 'O' },
  { action: 'Szukaj', keys: '/' },
  { action: 'Zamknij panel', keys: 'Esc' },
];

// Disclosure under the findings heading, drawn as the Components sheet: one row per action with its key chip.
// The keys are handled by useFindingShortcuts (Esc by the detail).
export function ShortcutLegend() {
  return (
    <details className="shortcuts">
      <summary>Skróty klawiszowe</summary>
      <dl>
        {SHORTCUTS.map((s) => (
          <div key={s.action}>
            <dt>
              {s.action}
              {s.hint && <small>{s.hint}</small>}
            </dt>
            <dd>
              <kbd>{s.keys}</kbd>
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
