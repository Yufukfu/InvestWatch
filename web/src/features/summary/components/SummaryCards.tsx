import { MODULE_LABEL } from '../../findings/components/labels';
import type { SummaryCounts } from '../model';
import { M2Coverage } from './M2Coverage';

type Props = {
  summary: SummaryCounts | undefined;
  /** The day shown in the eyebrow, already formatted (dd.mm.rrrr). */
  asOf: string;
  /** Opens the new high-risk findings. The summary counts every status, so the button shows no count. */
  onStartTriage: () => void;
};

function moduleLabel(module: string): string {
  const name = (MODULE_LABEL as Record<string, string | undefined>)[module];
  return name ? `${module} · ${name}` : module;
}

export function SummaryCards({ summary, asOf, onStartTriage }: Props) {
  if (!summary) return null;
  return (
    <section className="hero" aria-label="Podsumowanie">
      <p className="hero-eyebrow">PRZEGLĄD · {asOf}</p>
      <div className="hero-row">
        <p className="hero-figures">
          <span className="hero-value">{summary.total}</span> <span className="hero-label">
            zgłoszeń<span className="hero-sep">, z czego</span>
          </span>{' '}
          <span className="hero-value hero-value-risk">{summary.highRisk}</span>{' '}
          <span className="hero-label">wysokiego ryzyka</span>
        </p>
        {summary.highRisk > 0 && (
          <button type="button" className="btn btn-danger hero-triage" onClick={onStartTriage}>
            Rozpocznij triage <span aria-hidden="true">→</span>
          </button>
        )}
      </div>
      <ul className="kpis" aria-label="Wskaźniki">
        <li>
          <span className="kpi-value">{summary.newCount}</span>
          <span className="kpi-label">Nowe, bez decyzji</span>
        </li>
        {summary.byModule.map((m) => (
          <li key={m.module}>
            <span className="kpi-value">{m.count}</span>
            <span className="kpi-label">{moduleLabel(m.module)}</span>
          </li>
        ))}
      </ul>
      <M2Coverage coverage={summary.m2Coverage} />
    </section>
  );
}
