import { useGetStatsSummaryQuery } from '../../api/generated';

export function SummaryCards() {
  const { data } = useGetStatsSummaryQuery();
  if (!data) return null;
  const cards = [
    { label: 'Wszystkie zgłoszenia', value: data.total },
    { label: 'Wysokie ryzyko', value: data.by_risk_level.high ?? 0 },
    { label: 'Nowe', value: data.by_status.new ?? 0 },
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
