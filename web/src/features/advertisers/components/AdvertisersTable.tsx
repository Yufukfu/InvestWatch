import { findingsCount } from '../../findings/components/labels';
import type { AdvertiserRow, RelationNav } from '../model';
import { NO_FIRM_LABEL } from './labels';

type Props = RelationNav & { rows: AdvertiserRow[] };

// The "Tabela" view: every advertiser with every firm (and the findings with no matched firm). Each firm
// opens its relation page. Advertiser name, handle and contact come from scraped content: plain React text,
// each alone in a dir="auto" element, never a link (untrusted text rules in .claude/rules/web-dashboard.md).
export function AdvertisersTable({ rows, relationHref, onOpenRelation }: Props) {
  return (
    <div className="table-scroll">
      <table className="adv-table">
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
                  {r.name ?? r.handle ?? r.contact}
                </div>
                {r.name && r.handle && (
                  <div className="muted" dir="auto">
                    {r.handle}
                  </div>
                )}
              </td>
              <td>
                <ul className="firm-list">
                  {r.firms.map((f) => {
                    const relation = { advertiser: r.key, firm: f.key };
                    return (
                      <li key={f.key}>
                        <a
                          href={relationHref(relation)}
                          onClick={(e) => {
                            e.preventDefault();
                            onOpenRelation(relation);
                          }}
                        >
                          {f.name ? <span dir="auto">{f.name}</span> : <span className="muted">{NO_FIRM_LABEL}</span>}
                        </a>
                        {' – '}
                        <span>{findingsCount(f.count)}</span>
                      </li>
                    );
                  })}
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
  );
}
