import { useEffect, useId, useState } from 'react';
import { MODULES, PLATFORMS, RISK_LEVELS, STATUSES, type FindingFilters } from '../model';
import { MODULE_LABEL, PLATFORM_LABEL, RISK_LABEL, STATUS_LABEL } from './labels';

const SCORE_STEPS = [0.3, 0.5, 0.7, 0.9];
const SEARCH_DELAY_MS = 300;

type Props = {
  filters: FindingFilters;
  onChange: (patch: Partial<FindingFilters>) => void;
  onReset: () => void;
};

function activeCount(f: FindingFilters): number {
  return (
    [f.module, f.riskLevel, f.platform, f.scoreMin, f.dateFrom, f.dateTo, f.q].filter((v) => v !== undefined).length +
    f.status.length
  );
}

export function FindingsFilters({ filters, onChange, onReset }: Props) {
  const id = useId();
  const [text, setText] = useState(filters.q ?? '');
  const [seenQ, setSeenQ] = useState(filters.q);

  // An external change of q (reset, back button) replaces what is typed; adjusted during render.
  if (seenQ !== filters.q) {
    setSeenQ(filters.q);
    setText(filters.q ?? '');
  }

  useEffect(() => {
    const next = text.trim() || undefined;
    if (next === filters.q) return;
    const timer = setTimeout(() => onChange({ q: next }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, filters.q, onChange]);

  const toggleStatus = (s: (typeof STATUSES)[number]) =>
    onChange({ status: filters.status.includes(s) ? filters.status.filter((x) => x !== s) : [...filters.status, s] });

  const active = activeCount(filters);

  return (
    <form className="filters" role="search" aria-label="Filtry zgłoszeń" onSubmit={(e) => e.preventDefault()}>
      <div className="field field-search">
        <label htmlFor={`${id}-q`}>Szukaj</label>
        <input
          id={`${id}-q`}
          type="search"
          placeholder="Tytuł, firma, konto…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-module`}>Moduł</label>
        <select
          id={`${id}-module`}
          value={filters.module ?? ''}
          onChange={(e) => onChange({ module: (e.target.value || undefined) as FindingFilters['module'] })}
        >
          <option value="">Wszystkie</option>
          {MODULES.map((m) => (
            <option key={m} value={m}>
              {m} · {MODULE_LABEL[m]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-risk`}>Poziom ryzyka</label>
        <select
          id={`${id}-risk`}
          value={filters.riskLevel ?? ''}
          onChange={(e) => onChange({ riskLevel: (e.target.value || undefined) as FindingFilters['riskLevel'] })}
        >
          <option value="">Wszystkie</option>
          {RISK_LEVELS.map((r) => (
            <option key={r} value={r}>
              {RISK_LABEL[r]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-platform`}>Platforma</label>
        <select
          id={`${id}-platform`}
          value={filters.platform ?? ''}
          onChange={(e) => onChange({ platform: (e.target.value || undefined) as FindingFilters['platform'] })}
        >
          <option value="">Wszystkie</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {PLATFORM_LABEL[p]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-score`}>Minimalny wynik</label>
        <select
          id={`${id}-score`}
          value={filters.scoreMin === undefined ? '' : String(filters.scoreMin)}
          onChange={(e) => onChange({ scoreMin: e.target.value === '' ? undefined : Number(e.target.value) })}
        >
          <option value="">Dowolny</option>
          {/* A value from a shared link that is not a preset still shows as selected. */}
          {filters.scoreMin !== undefined && !SCORE_STEPS.includes(filters.scoreMin) && (
            <option value={String(filters.scoreMin)}>≥ {filters.scoreMin}</option>
          )}
          {SCORE_STEPS.map((s) => (
            <option key={s} value={String(s)}>
              ≥ {s}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-from`}>Od dnia</label>
        <input
          id={`${id}-from`}
          type="date"
          value={filters.dateFrom ?? ''}
          max={filters.dateTo}
          onChange={(e) => onChange({ dateFrom: e.target.value || undefined })}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-to`}>Do dnia</label>
        <input
          id={`${id}-to`}
          type="date"
          value={filters.dateTo ?? ''}
          min={filters.dateFrom}
          onChange={(e) => onChange({ dateTo: e.target.value || undefined })}
        />
      </div>
      <fieldset className="field field-status">
        <legend>Status</legend>
        <div className="chips">
          {STATUSES.map((s) => (
            <label key={s} className="chip">
              <input type="checkbox" checked={filters.status.includes(s)} onChange={() => toggleStatus(s)} />
              <span>{STATUS_LABEL[s]}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {active > 0 && (
        <div className="filters-actions">
          <button type="button" className="btn btn-ghost" onClick={onReset}>
            Wyczyść filtry ({active})
          </button>
        </div>
      )}
    </form>
  );
}
