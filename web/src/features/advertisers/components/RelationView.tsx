import { formatScore } from '../../../format/score';
import { detectedParts, platformLabel } from '../../findings/components/labels';
import { RiskBadge } from '../../findings/components/RiskBadge';
import { advertiserLabel } from '../aggregate';
import { NO_FIRM, type AdvertiserFinding, type AdvertiserRow, type Relation, type RelationNav } from '../model';
import { NO_FIRM_LABEL, plural } from './labels';

type Props = RelationNav & {
  relation: Relation;
  // The advertiser as grouped under the current filters; undefined when it is not in the loaded data.
  row: AdvertiserRow | undefined;
  // The relation's findings, newest first.
  findings: AdvertiserFinding[];
  onBack: () => void;
  onOpenFinding: (id: string) => void;
};

function DetectedAt({ iso }: { iso: string | undefined }) {
  if (!iso) return null;
  const p = detectedParts(iso);
  return (
    <time dateTime={iso} title="Czas UTC">
      {p ? `${p.dayMonth}.${p.year} · ${p.time}` : iso}
    </time>
  );
}

function BackLink({ onBack }: { onBack: () => void }) {
  return (
    <button type="button" className="adv-back" onClick={onBack}>
      <span aria-hidden="true">←</span> Powiązania
    </button>
  );
}

// "Wybrana relacja": the findings of one advertiser for one firm (or for all of its firms), opened from an
// edge, a firm in the table, or the side table's link. Rows open the finding detail on the findings page.
export function RelationView({ relation, row, findings, onBack, onOpenFinding, relationHref, onOpenRelation }: Props) {
  if (!row)
    return (
      <div className="adv-relation">
        <BackLink onBack={onBack} />
        <p className="state state-empty" role="status">
          Nie znaleziono tej relacji w wczytanych zgłoszeniach M1 dla wybranych filtrów.
        </p>
      </div>
    );
  const firm = relation.firm === undefined ? undefined : row.firms.find((f) => f.key === relation.firm);
  // Undefined for a firm key not among the advertiser's firms (an old link, or filtered out).
  const firmName = relation.firm === NO_FIRM ? NO_FIRM_LABEL : firm?.name;
  const others = row.firms.filter((f) => f.key !== NO_FIRM && f.name && f.key !== relation.firm);
  const n = findings.length;
  return (
    <div className="adv-relation">
      <BackLink onBack={onBack} />
      <p className="hero-eyebrow">{relation.firm === undefined ? 'WYBRANY REKLAMODAWCA' : 'WYBRANA RELACJA'}</p>
      <h2 className="adv-relation-title">
        <span className="hero-value hero-value-risk">{n}</span>{' '}
        <span className="hero-label">{plural(n, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń')}:</span>{' '}
        <span className="adv-relation-name" dir="auto">
          {advertiserLabel(row)}
        </span>
        {relation.firm !== undefined && (
          <>
            {' '}
            <span className="adv-relation-arrow" aria-hidden="true">
              →
            </span>{' '}
            <span className="visually-hidden">promuje</span>{' '}
            <span className="adv-relation-name" dir="auto">
              {firmName ?? 'nieznana firma'}
            </span>
          </>
        )}
      </h2>
      <div className="adv-relation-meta">
        <p>
          {others.length === 0 ? (
            relation.firm === undefined ? (
              'Reklamodawca nie promuje firm z rejestru w tych zgłoszeniach.'
            ) : (
              'Ten reklamodawca nie promuje innych firm z rejestru.'
            )
          ) : (
            <>
              {relation.firm === undefined ? 'Reklamodawca promuje ' : 'Ten sam reklamodawca promuje jeszcze '}
              <strong>{`${others.length} ${plural(others.length, 'firmę', 'firmy', 'firm')}`}</strong>:{' '}
              {others.map((f, i) => (
                <span key={f.key}>
                  {i > 0 && ', '}
                  <a
                    href={relationHref({ advertiser: row.key, firm: f.key })}
                    onClick={(e) => {
                      e.preventDefault();
                      onOpenRelation({ advertiser: row.key, firm: f.key });
                    }}
                  >
                    <span dir="auto">{f.name}</span>
                  </a>{' '}
                  ({f.count})
                </span>
              ))}
            </>
          )}
        </p>
        {relation.firm !== undefined && (
          <a
            className="btn adv-profile"
            href={relationHref({ advertiser: row.key })}
            onClick={(e) => {
              e.preventDefault();
              onOpenRelation({ advertiser: row.key });
            }}
          >
            Pokaż cały profil reklamodawcy <span aria-hidden="true">→</span>
          </a>
        )}
      </div>
      {n === 0 ? (
        <p className="state state-empty" role="status">
          Brak zgłoszeń tej relacji dla wybranych filtrów.
        </p>
      ) : (
        <div className="table-scroll">
          {/* Roles are explicit: on a phone the rows become cards (display changes), which drops implicit table roles. */}
          <table className="adv-relation-table" role="table">
            <thead>
              <tr role="row">
                <th scope="col" role="columnheader">Ryzyko</th>
                <th scope="col" role="columnheader">Tytuł</th>
                <th scope="col" role="columnheader">Platforma</th>
                <th scope="col" role="columnheader">Wynik</th>
                <th scope="col" role="columnheader" aria-sort="descending">
                  Wykryto <span aria-hidden="true">↓</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id} role="row" className={f.riskLevel ? `row-${f.riskLevel}` : undefined}>
                  <td role="cell" className="rel-risk">
                    <RiskBadge level={f.riskLevel} />
                  </td>
                  <td role="cell" className="adv-relation-title-cell">
                    <button type="button" className="link" dir="auto" onClick={() => onOpenFinding(f.id)}>
                      {f.title ?? f.id}
                    </button>
                  </td>
                  <td role="cell" className="rel-platform">{f.platform ? platformLabel(f.platform) : ''}</td>
                  <td role="cell" className="rel-score">
                    {f.score !== undefined && (
                      <span className="score mono">
                        <span className="score-bar" aria-hidden="true">
                          <span style={{ width: `${Math.round(Math.min(1, Math.max(0, f.score)) * 100)}%` }} />
                        </span>
                        <span>{formatScore(f.score)}</span>
                      </span>
                    )}
                  </td>
                  <td role="cell" className="mono adv-relation-date">
                    <DetectedAt iso={f.detectedAt} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
