import { useCallback, useEffect, useMemo } from 'react';
import { useGetFindingsQuery, type Finding } from '../../../api/generated';
import type { FindingFilters, FindingRow } from '../model';
import { hasTriageFlag, parseFilters, parseSelected, serializeUrl, toQueryArg, triageUrl, withFilter } from './findingsUrl';
import { FINDINGS_SECTION, goToSection } from '../../../url/section';
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
  const { data, currentData, isLoading, isFetching, isError } = useGetFindingsQuery(toQueryArg(filters));

  // Triage is a one-shot: once the list for the triage filters has arrived, open its first row (none when
  // it is empty or failed) and rewrite the URL without the flag. currentData belongs to the current
  // arguments only, so the previous list is never mistaken for the triage result.
  const triage = hasTriageFlag(search);
  useEffect(() => {
    if (!triage) return;
    if (isError) {
      push(serializeUrl(filters, undefined), { replace: true });
      return;
    }
    if (!currentData) return;
    push(serializeUrl(filters, currentData.items[0]?.id), { replace: true });
  }, [triage, isError, currentData, filters, push]);

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

// The summary's triage action: show the new high-risk findings and open the first one (see the effect above).
export function useStartTriage(): () => void {
  const [, push] = useUrlSearch();
  return useCallback(() => {
    push(triageUrl());
    goToSection(FINDINGS_SECTION);
  }, [push]);
}
