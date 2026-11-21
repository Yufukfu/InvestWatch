import { useCallback, useMemo } from 'react';
import { useGetFindingsQuery, type Finding } from '../../../api/generated';
import type { FindingFilters, FindingRow } from '../model';
import { parseFilters, parseSelected, serializeUrl, toQueryArg, withFilter } from './findingsUrl';
import { useUrlSearch } from './useUrlSearch';

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
  // While a new filter loads the previous rows are not shown as current: `currentData` is undefined then.
  const { currentData, isLoading, isFetching, isError } = useGetFindingsQuery(toQueryArg(filters));

  const setFilters = useCallback(
    (patch: Partial<FindingFilters>) => push(serializeUrl(withFilter(filters, patch), selectedId)),
    [push, filters, selectedId],
  );
  const resetFilters = useCallback(
    () => push(serializeUrl({ ...parseFilters(''), pageSize: filters.pageSize }, selectedId)),
    [push, filters.pageSize, selectedId],
  );
  const select = useCallback((id: string | undefined) => push(serializeUrl(filters, id)), [push, filters]);

  return {
    rows: isError ? undefined : currentData?.items.map(toRow),
    total: isError ? undefined : currentData?.total,
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
