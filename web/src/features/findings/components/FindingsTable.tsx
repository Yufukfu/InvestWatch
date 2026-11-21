import type { FindingRow, FindingStatus } from '../model';

const STATUS_LABEL: Record<FindingStatus, string> = {
  new: 'Nowe',
  in_review: 'W analizie',
  confirmed: 'Potwierdzone',
  false_positive: 'Fałszywy alarm',
  closed: 'Zamknięte',
};

type Props = { rows: FindingRow[] | undefined; isLoading: boolean; isError: boolean };

// Scraped content is untrusted: every value is rendered as React text, never as HTML.
export function FindingsTable({ rows, isLoading, isError }: Props) {
  if (isLoading) return <p>Ładowanie…</p>;
  if (isError || !rows) return <p role="alert">Nie udało się pobrać zgłoszeń.</p>;
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
        {rows.map((f) => (
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
