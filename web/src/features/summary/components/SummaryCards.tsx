import type { SummaryCounts } from '../model';

export function SummaryCards({ summary }: { summary: SummaryCounts | undefined }) {
  if (!summary) return null;
  return (
    <section className="hero" aria-label="Podsumowanie">
      <div className="hero-figures">
        <p className="hero-figure">
          <span className="hero-value">{summary.total}</span> <span className="hero-label">zgłoszeń</span>
        </p>
        <p className="hero-figure hero-risk">
          <span className="hero-value">{summary.highRisk}</span> <span className="hero-label">wysokiego ryzyka</span>
        </p>
        <p className="hero-new">
          <span className="hero-new-value">{summary.newCount}</span> nowych
        </p>
      </div>
      <ul className="hero-modules" aria-label="Zgłoszenia według modułów">
        {summary.byModule.map((m) => (
          <li key={m.module}>
            <span className="module">{m.module}</span> <span className="hero-module-count">{m.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
