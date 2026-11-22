import { STATUSES } from '../model';
import { STATUS_LABEL } from './labels';

const SHORTCUTS: { key: string; meaning: string }[] = [
  { key: 'J', meaning: 'Następne zgłoszenie' },
  { key: 'K', meaning: 'Poprzednie zgłoszenie' },
  ...STATUSES.map((s, i) => ({ key: String(i + 1), meaning: `Status: ${STATUS_LABEL[s]}` })),
  { key: 'O', meaning: 'Otwórz źródło' },
  { key: '/', meaning: 'Szukaj' },
  { key: 'Esc', meaning: 'Zamknij szczegóły' },
];

// Plain disclosure under the findings heading; the keys are handled by useFindingShortcuts (Esc by the detail).
export function ShortcutLegend() {
  return (
    <details className="shortcuts">
      <summary>Skróty klawiszowe</summary>
      <dl>
        {SHORTCUTS.map((s) => (
          <div key={s.key}>
            <dt>
              <kbd>{s.key}</kbd>
            </dt>
            <dd>{s.meaning}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
