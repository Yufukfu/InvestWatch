import type { AdvertiserRow, RelationNav } from '../model';
import { advertiserLabel } from '../aggregate';
import { NO_FIRM } from '../model';
import { plural } from './labels';

type Props = RelationNav & {
  rows: AdvertiserRow[];
  matchedFindings: number;
  selected: string | undefined;
  onSelect: (key: string) => void;
};

const matchedFirms = (r: AdvertiserRow) => r.firms.filter((f) => f.key !== NO_FIRM && f.name);

// "Najczęstsi reklamodawcy": the advertisers by number of findings. A row (or its handle button) picks the
// advertiser whose edges the graph highlights; the link under the table opens all of its findings.
export function TopAdvertisers({ rows, matchedFindings, selected, onSelect, relationHref, onOpenRelation }: Props) {
  const current = rows.find((r) => r.key === selected);
  return (
    <section className="adv-top" aria-labelledby="adv-top-heading">
      <h3 id="adv-top-heading">Najczęstsi reklamodawcy</h3>
      <p className="adv-top-sub">
        {`${matchedFindings} ${plural(matchedFindings, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń')} z dopasowaną firmą · kliknij wiersz, by podświetlić relacje`}
      </p>
      <div className="table-scroll">
        <table className="adv-top-table">
          <thead>
            <tr>
              <th scope="col">Reklamodawca</th>
              <th scope="col" className="num">
                Firmy
              </th>
              <th scope="col" className="num" aria-sort="descending">
                Zgł. <span aria-hidden="true">↓</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const firms = matchedFirms(r);
              return (
                <tr key={r.key} className={r.key === selected ? 'selected' : undefined} onClick={() => onSelect(r.key)}>
                  <td>
                    <button type="button" className="adv-top-handle" aria-pressed={r.key === selected} onClick={(e) => { e.stopPropagation(); onSelect(r.key); }}>
                      <span dir="auto">{advertiserLabel(r)}</span>
                    </button>
                    {/* The mockup marks a repeat advertiser by its red firm count and the legend; the text is for assistive tech. */}
                    {r.repeat && <span className="visually-hidden"> (powtarzający się)</span>}
                    {firms.length > 0 && (
                      <span className="adv-top-firms">
                        {firms.map((f, i) => (
                          <span key={f.key}>
                            {i > 0 && ' · '}
                            <span dir="auto">{f.name}</span>
                          </span>
                        ))}
                      </span>
                    )}
                  </td>
                  <td className={r.repeat ? 'num adv-firms-repeat' : 'num'}>{firms.length}</td>
                  <td className="num">{r.count}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {current && (
        <a
          className="adv-top-link"
          href={relationHref({ advertiser: current.key })}
          onClick={(e) => {
            e.preventDefault();
            onOpenRelation({ advertiser: current.key });
          }}
        >
          Zobacz zgłoszenia <span dir="auto">{advertiserLabel(current)}</span> <span aria-hidden="true">→</span>
        </a>
      )}
    </section>
  );
}
