import { useCallback, useMemo } from 'react';
import { useGetFindingsQuery, type Finding } from '../../../api/generated';
import type { FindingFilters, FindingRow } from '../model';
import { parseFilters, parseSelected, serializeUrl, toQueryArg, withFilter } from './findingsUrl';
import { useUrlSearch } from '../../../url/useUrlSearch';

// Only http(s) URLs give a host; scraped data may hold anything else.
function httpHost(url: string): string | undefined {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.hostname : undefined;
  } catch {
    return undefined;
  }
}

// The generated DTO stops here. `module` and `status` are assigned from the generated unions, so a
// contract change that adds a value fails to compile in this file instead of leaking into components.
function toRow(f: Finding): FindingRow {
  return {
    id: f.id,
    module: f.module,
    title: f.title,
    platform: f.platform,
    score: f.score,
    riskLevel: f.risk_level,
    status: f.status,
    detectedAt: f.detected_at,
    documentId: f.document_id,
    url: f.url,
    host: httpHost(f.url),
  };
}

export type FindingsState = {
  rows: FindingRow[] | undefined;
  total: number | undefined;
  filters: FindingFilters;
  setFilters: (patch: Partial<FindingFilters>) => void;
  resetFilters: () => void;
  selectedId: string | undefined;
  select: (id: string | undefined) => void;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
};

export function useFindings(): FindingsState {
  const [search, push] = useUrlSearch();
  const filters = useMemo(() => parseFilters(search), [search]);
  const selectedId = useMemo(() => parseSelected(search), [search]);
  // While the next page or filter loads, the last result stays (marked busy by the table), so the
  // sort header or pager button that had focus is not unmounted. A failed request clears it.
  const { data, isLoading, isFetching, isError } = useGetFindingsQuery(toQueryArg(filters));

  const setFilters = useCallback(
    (patch: Partial<FindingFilters>) => {
      const searchOnly = Object.keys(patch).length === 1 && 'q' in patch;
      push(serializeUrl(withFilter(filters, patch), selectedId), { replace: searchOnly });
    },
    [push, filters, selectedId],
  );
  const resetFilters = useCallback(
    () => push(serializeUrl({ ...parseFilters(''), pageSize: filters.pageSize }, selectedId)),
    [push, filters.pageSize, selectedId],
  );
  const select = useCallback((id: string | undefined) => push(serializeUrl(filters, id)), [push, filters]);

  return {
    rows: isError ? undefined : data?.items.map(toRow),
    total: isError ? undefined : data?.total,
    filters,
    setFilters,
    resetFilters,
    selectedId,
    select,
    isLoading,
    isFetching,
    isError,
  };
}
