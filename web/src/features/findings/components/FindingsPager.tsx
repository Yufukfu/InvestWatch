import { useId } from 'react';
import { PAGE_SIZES } from '../model';

type Props = {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
};

export function FindingsPager({ page, pageSize, total, onPage, onPageSize }: Props) {
  const id = useId();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className="pager" aria-label="Stronicowanie">
      <button type="button" className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Poprzednia strona">
        ‹ Poprzednia
      </button>
      <span className="pager-pos" aria-live="polite">
        Strona {page} z {pages}
      </span>
      <button type="button" className="btn" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Następna strona">
        Następna ›
      </button>
      <span className="pager-size">
        <label htmlFor={`${id}-size`}>Na stronie</label>
        <select id={`${id}-size`} value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </span>
    </nav>
  );
}
