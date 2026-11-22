import { useId } from 'react';
import { isolate } from '../../../format/bidi';
import type { RuleOutcome, RuleView } from '../model';

// The four rule results in the legend's order, with their Polish names (Paper mockup, components-1440).
const RESULTS: ReadonlyArray<[RuleOutcome, string]> = [
  ['fail', 'Naruszenie'],
  ['uncertain', 'Niepewne'],
  ['pass', 'Zgodne'],
  ['not_applicable', 'Nie dotyczy'],
];
const RESULT_LABEL = Object.fromEntries(RESULTS) as Record<RuleOutcome, string>;
const NO_BASIS = 'brak podstawy prawnej';

// "Pokrycie reguł M2": one square per rule the finding reports, in API order, coloured by result. The rule id in
// each square and the legend's words and counts carry the meaning without colour. Squares are buttons so the
// legal basis shows on keyboard focus as well as on hover (CSS); rule ids, names and legal bases come from the
// API, so they are text with dir="auto", and isolated inside the accessible name (format/bidi).
export function RuleGrid({ rules }: { rules: RuleView[] }) {
  const headingId = useId();
  if (rules.length === 0) return null;
  const counts = new Map<RuleOutcome, number>();
  for (const r of rules) counts.set(r.result, (counts.get(r.result) ?? 0) + 1);
  return (
    <section className="detail-section rule-grid" aria-labelledby={headingId}>
      <div className="rule-grid-head">
        <h3 id={headingId} className="rule-grid-title">
          POKRYCIE REGUŁ M2 · {rules.length} WYMOGÓW
        </h3>
        <p className="rule-grid-hint">Najedź na pole lub przejdź do niego klawiszem Tab, aby zobaczyć podstawę prawną</p>
      </div>
      <ul className="rule-cells">
        {rules.map((r) => {
          const label = RESULT_LABEL[r.result] ?? r.result;
          const basis = r.legalBasis ? isolate(r.legalBasis) : NO_BASIS;
          return (
            <li key={r.ruleId} className="rule-cell-wrap">
              <button
                type="button"
                className={`rule-cell cell-${r.result}`}
                aria-label={`${isolate(r.ruleId)}, ${isolate(r.name)}: ${label}. Podstawa prawna: ${basis}`}
              >
                <span dir="auto">{r.ruleId}</span>
              </button>
              <span role="tooltip" className="rule-tip">
                <span className="rule-tip-head">
                  <span dir="auto">{r.ruleId}</span> · {label}
                </span>
                {r.legalBasis ? <span dir="auto">{r.legalBasis}</span> : <span>{NO_BASIS}</span>}
              </span>
            </li>
          );
        })}
      </ul>
      <ul className="rule-legend" aria-label="Legenda">
        {RESULTS.map(([result, label]) => (
          <li key={result}>
            <span className={`rule-swatch cell-${result}`} aria-hidden="true" />
            {label} {counts.get(result) ?? 0}
          </li>
        ))}
      </ul>
    </section>
  );
}
