import { findingsCount } from '../../findings/components/labels';
import { FINDINGS_CAP, type AdvertisersView } from '../model';

// Advertiser name and handle come from scraped content: plain React text, each alone in a dir="auto"
// element, never a link (untrusted text rules in .claude/rules/web-dashboard.md).
export function AdvertisersTable({ rows, loaded, total, isLoading, isError }: AdvertisersView) {
  if (isError) return <p className="state" role="alert">Nie udało się pobrać danych o reklamodawcach.</p>;
  if (isLoading || !rows) return <p className="state" role="status">Ładowanie…</p>;
  const truncated = total !== undefined && total > loaded;
  return (
    <>
      <p className="findings-count">
        {`Przeanalizowane zgłoszenia M1: ${loaded} z ${total ?? loaded} (limit ${FINDINGS_CAP}).`}
        {truncated && ' Starsze zgłoszenia pominięto.'}
      </p>
      {rows.length === 0 ? (
        <p className="state state-empty" role="status">
          Brak reklamodawców w zgłoszeniach M1.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="findings advertisers">
            <thead>
              <tr>
                <th scope="col">Reklamodawca</th>
                <th scope="col">Promowane firmy</th>
                <th scope="col">Zgłoszenia</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className={r.repeat ? 'repeat' : undefined}>
                  <td>
                    <div className="advertiser-name" dir="auto">
                      {r.name ?? r.handle}
                    </div>
                    {r.name && r.handle && (
                      <div className="muted" dir="auto">
                        {r.handle}
                      </div>
                    )}
                  </td>
                  <td>
                    <ul className="firm-list">
                      {r.firms.map((f) => (
                        <li key={f.key}>
                          {f.name ? <span dir="auto">{f.name}</span> : <span className="muted">bez dopasowanej firmy</span>}
                          {' – '}
                          <span>{findingsCount(f.count)}</span>
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    <span className="advertiser-count">{r.count}</span>
                    {r.repeat && <span className="badge badge-repeat">Powtarzający się</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
