import { useEffect, useId, useState } from 'react';
import { isolate } from '../../../format/bidi';
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

type ActiveChip = { key: string; label: string; clears: Partial<FindingFilters>; status?: boolean };

// One chip per active filter, in the order the filters are listed; a status chip removes only its own status.
function activeChips(f: FindingFilters): ActiveChip[] {
  const chips: ActiveChip[] = f.status.map((s) => ({
    key: `status-${s}`,
    label: STATUS_LABEL[s],
    clears: { status: f.status.filter((x) => x !== s) },
    status: true,
  }));
  if (f.riskLevel) chips.push({ key: 'risk', label: RISK_LABEL[f.riskLevel], clears: { riskLevel: undefined } });
  if (f.module) chips.push({ key: 'module', label: f.module, clears: { module: undefined } });
  if (f.platform) chips.push({ key: 'platform', label: PLATFORM_LABEL[f.platform], clears: { platform: undefined } });
  if (f.scoreMin !== undefined) chips.push({ key: 'score', label: `≥ ${f.scoreMin}`, clears: { scoreMin: undefined } });
  if (f.dateFrom) chips.push({ key: 'from', label: `od ${f.dateFrom}`, clears: { dateFrom: undefined } });
  if (f.dateTo) chips.push({ key: 'to', label: `do ${f.dateTo}`, clears: { dateTo: undefined } });
  if (f.q) chips.push({ key: 'q', label: `„${f.q}”`, clears: { q: undefined } });
  return chips;
}

export function FindingsFilters({ filters, onChange, onReset }: Props) {
  const id = useId();
  const [text, setText] = useState(filters.q ?? '');
  const [seenQ, setSeenQ] = useState(filters.q);
  // Only meaningful below 1024px, where the CSS hides the fields behind the Filtry button until it is opened.
  const [open, setOpen] = useState(false);

  // An external change of q (back button, shared link) replaces what is typed; adjusted during render.
  // Our own settled search comes back trimmed, so only resync when it really differs from the box,
  // or the space the user just typed would be eaten.
  if (seenQ !== filters.q) {
    setSeenQ(filters.q);
    if (filters.q !== (text.trim() || undefined)) setText(filters.q ?? '');
  }

  const reset = () => {
    // Emptying the box first makes the debounce effect cancel a pending search.
    setText('');
    onReset();
  };

  useEffect(() => {
    const next = text.trim() || undefined;
    if (next === filters.q) return;
    const timer = setTimeout(() => onChange({ q: next }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, filters.q, onChange]);

  const toggleStatus = (s: (typeof STATUSES)[number]) =>
    onChange({ status: filters.status.includes(s) ? filters.status.filter((x) => x !== s) : [...filters.status, s] });

  const active = activeCount(filters);
  const chips = activeChips(filters);

  return (
    <form
      className="filters"
      role="search"
      aria-label="Filtry zgłoszeń"
      onSubmit={(e) => e.preventDefault()}
    >
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
      <button
        type="button"
        className="btn filters-toggle"
        aria-expanded={open}
        aria-controls={`${id}-more`}
        onClick={() => setOpen((o) => !o)}
      >
        Filtry
        {active > 0 && (
          <>
            {' '}
            <span className="filters-toggle-count">{active}</span>
          </>
        )}
      </button>
      {chips.length > 0 && (
        <div className="filter-chips" role="group" aria-label="Aktywne filtry">
          {chips.map((c) => (
            <button
              key={c.key}
              type="button"
              className={c.status ? 'filter-chip filter-chip-status' : 'filter-chip'}
              aria-label={`Usuń filtr: ${c.key === 'q' ? isolate(c.label) : c.label}`}
              onClick={() => onChange(c.clears)}
            >
              <span dir="auto">{c.label}</span> <span aria-hidden="true">✕</span>
            </button>
          ))}
        </div>
      )}
      <div id={`${id}-more`} className={open ? 'filters-more filters-open' : 'filters-more'}>
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
            <button type="button" className="btn btn-ghost" onClick={reset}>
              Wyczyść filtry ({active})
            </button>
          </div>
        )}
      </div>
    </form>
  );
}
