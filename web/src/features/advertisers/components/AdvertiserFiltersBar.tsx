import { useId } from 'react';
import { MIN_FINDINGS_OPTIONS, PERIODS, type AdvertiserFilters, type AdvertiserPeriod } from '../filters';
import type { RiskLevel } from '../model';

export type AdvertiserView = 'graph' | 'table';

const PERIOD_LABEL: Record<AdvertiserPeriod, string> = { '7': 'Ostatnie 7 dni', '30': 'Ostatnie 30 dni', '90': 'Ostatnie 90 dni', all: 'Wszystko' };
const RISK_OPTIONS: Array<{ value: RiskLevel | 'all'; label: string }> = [
  { value: 'all', label: 'Wszystkie' },
  { value: 'high', label: 'Wysokie' },
  { value: 'medium', label: 'Średnie' },
  { value: 'low', label: 'Niskie' },
];

type Props = {
  filters: AdvertiserFilters;
  onChange: (patch: Partial<AdvertiserFilters>) => void;
  view: AdvertiserView;
  onViewChange: (view: AdvertiserView) => void;
};

export function AdvertiserFiltersBar({ filters, onChange, view, onViewChange }: Props) {
  const id = useId();
  return (
    <div className="adv-filters" role="group" aria-label="Filtry powiązań">
      <div className="adv-filter">
        <label htmlFor={`${id}-period`}>Okres</label>
        <select id={`${id}-period`} className="adv-select-strong" value={filters.period} onChange={(e) => onChange({ period: e.target.value as AdvertiserPeriod })}>
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {PERIOD_LABEL[p]}
            </option>
          ))}
        </select>
      </div>
      <span className="adv-filters-sep" aria-hidden="true" />
      <div className="adv-filter">
        <label htmlFor={`${id}-risk`}>Ryzyko</label>
        <select id={`${id}-risk`} value={filters.risk} onChange={(e) => onChange({ risk: e.target.value as AdvertiserFilters['risk'] })}>
          {RISK_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="adv-filter">
        <label htmlFor={`${id}-min`} className="visually-hidden">
          Minimalna liczba zgłoszeń
        </label>
        <select id={`${id}-min`} value={filters.minFindings} onChange={(e) => onChange({ minFindings: Number(e.target.value) })}>
          {MIN_FINDINGS_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {`Min. zgłoszeń: ${n}`}
            </option>
          ))}
        </select>
      </div>
      <label className="adv-check">
        <input type="checkbox" checked={filters.repeatOnly} onChange={(e) => onChange({ repeatOnly: e.target.checked })} />
        Tylko powtarzający się
      </label>
      <div className="segmented adv-view" role="group" aria-label="Widok">
        <button type="button" aria-pressed={view === 'graph'} onClick={() => onViewChange('graph')}>
          Graf
        </button>
        <button type="button" aria-pressed={view === 'table'} onClick={() => onViewChange('table')}>
          Tabela
        </button>
      </div>
    </div>
  );
}
