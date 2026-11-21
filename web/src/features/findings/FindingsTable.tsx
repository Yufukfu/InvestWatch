import { useGetFindingsQuery } from '../../api/generated';

const STATUS_LABEL: Record<string, string> = {
  new: 'Nowe',
  in_review: 'W analizie',
  confirmed: 'Potwierdzone',
  false_positive: 'Fałszywy alarm',
  closed: 'Zamknięte',
};

// Scraped content is untrusted: every value is rendered as React text, never as HTML.
export function FindingsTable() {
  const { data, isLoading, isError } = useGetFindingsQuery({ page: 1, pageSize: 50 });
  if (isLoading) return <p>Ładowanie…</p>;
  if (isError || !data) return <p role="alert">Nie udało się pobrać zgłoszeń.</p>;
  return (
    <table className="findings">
      <thead>
        <tr>
          <th>Moduł</th>
          <th>Tytuł</th>
          <th>Platforma</th>
          <th>Wynik</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {data.items.map((f) => (
          <tr key={f.id}>
            <td>{f.module}</td>
            <td>{f.title}</td>
            <td>{f.platform}</td>
            <td>{f.score.toFixed(2)}</td>
            <td>{STATUS_LABEL[f.status] ?? f.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
