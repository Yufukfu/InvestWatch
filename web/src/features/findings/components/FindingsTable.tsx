import { formatScore } from '../../../format/score';
import type { FindingRow, FindingSort } from '../model';
import { findingsCount, formatDetected, MODULE_LABEL, platformLabel, STATUS_LABEL } from './labels';
import { RiskBadge } from './RiskBadge';

type Props = {
  rows: FindingRow[] | undefined;
  total: number | undefined;
  sort: FindingSort;
  onSort: (sort: FindingSort) => void;
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  onReset: () => void;
  onFirstPage: () => void;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
};

type SortKey = 'detected_at' | 'score';

function SortHeader({ label, field, sort, onSort }: { label: string; field: SortKey; sort: FindingSort; onSort: Props['onSort'] }) {
  const active = sort === field || sort === `-${field}`;
  const descending = sort === `-${field}`;
  // First click sorts descending (newest, highest); a second click flips the direction.
  const next: FindingSort = active && descending ? field : `-${field}`;
  return (
    <th scope="col" role="columnheader" className={`col-${field === 'score' ? 'score' : 'date'}`} aria-sort={active ? (descending ? 'descending' : 'ascending') : 'none'}>
      <button type="button" className="sort" onClick={() => onSort(next)}>
        {label}
        <span aria-hidden="true" className="sort-arrow">
          {active ? (descending ? '↓' : '↑') : '↕'}
        </span>
      </button>
    </th>
  );
}

// Scraped content is untrusted: every value is rendered as React text, never as HTML.
export function FindingsTable({ rows, total, sort, onSort, selectedId, onSelect, onReset, onFirstPage, isLoading, isFetching, isError }: Props) {
  if (isError) return <p className="state" role="alert">Nie udało się pobrać zgłoszeń.</p>;
  if (isLoading || !rows) return <p className="state" role="status">Ładowanie…</p>;
  // Rows can be empty with total > 0 on a page past the end (old link, or the last row changed status).
  if (rows.length === 0 && (total ?? 0) > 0)
    return (
      <div className="state state-empty" role="status">
        <p>Na tej stronie nie ma już zgłoszeń.</p>
        <button type="button" className="btn" onClick={onFirstPage}>
          Wróć do pierwszej strony
        </button>
      </div>
    );
  if (rows.length === 0)
    return (
      <div className="state state-empty" role="status">
        <p>Żadne zgłoszenie nie pasuje do filtrów.</p>
        <button type="button" className="btn" onClick={onReset}>
          Wyczyść filtry
        </button>
      </div>
    );
  return (
    <>
      <p className="findings-count">{findingsCount(total ?? rows.length)}</p>
      <div className="table-scroll" aria-busy={isFetching}>
        {/* Roles are explicit: the card layout on a phone sets display on table parts, which drops their implicit roles. */}
        <table className="findings" role="table">
          <thead>
            <tr role="row">
              <th scope="col" role="columnheader" className="col-risk">Ryzyko</th>
              <th scope="col" role="columnheader" className="col-title">Tytuł</th>
              <th scope="col" role="columnheader" className="col-module">Moduł</th>
              <th scope="col" role="columnheader" className="col-platform">Platforma</th>
              <SortHeader label="Wynik" field="score" sort={sort} onSort={onSort} />
              <th scope="col" role="columnheader" className="col-status">Status</th>
              <SortHeader label="Wykryto" field="detected_at" sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr
                key={f.id}
                role="row"
                aria-current={f.id === selectedId ? 'true' : undefined}
                className={[f.id === selectedId && 'selected', f.riskLevel && `row-${f.riskLevel}`].filter(Boolean).join(' ') || undefined}
              >
                <td role="cell" className="col-risk">
                  <RiskBadge level={f.riskLevel} />
                </td>
                <td role="cell" className="col-title">
                  <button type="button" className="link" onClick={() => onSelect(f.id)}>
                    {f.title}
                  </button>
                </td>
                <td role="cell" className="col-module">
                  <span className="module" title={MODULE_LABEL[f.module]}>
                    {f.module}
                  </span>
                </td>
                <td role="cell" className="col-platform">{platformLabel(f.platform)}</td>
                <td role="cell" className="col-score">
                  <span className="score mono">
                    <span className="score-bar" aria-hidden="true">
                      <span style={{ width: `${Math.round(Math.min(1, Math.max(0, f.score)) * 100)}%` }} />
                    </span>
                    <span>{formatScore(f.score)}</span>
                  </span>
                </td>
                <td role="cell" className="col-status">
                  <span className={`status status-${f.status}`}>{STATUS_LABEL[f.status] ?? f.status}</span>
                </td>
                <td role="cell" className="col-date mono">
                  <time dateTime={f.detectedAt} title="Czas UTC">
                    {formatDetected(f.detectedAt)}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
