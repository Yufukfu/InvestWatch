import type { SummaryCounts } from '../model';

export function SummaryCards({ summary }: { summary: SummaryCounts | undefined }) {
  if (!summary) return null;
  const cards = [
    { label: 'Wszystkie zgłoszenia', value: summary.total },
    { label: 'Wysokie ryzyko', value: summary.highRisk },
    { label: 'Nowe', value: summary.newCount },
  ];
  return (
    <section className="cards" aria-label="Podsumowanie">
      {cards.map((c) => (
        <div key={c.label} className="card">
          <div className="card-value">{c.value}</div>
          <div className="card-label">{c.label}</div>
        </div>
      ))}
    </section>
  );
}
