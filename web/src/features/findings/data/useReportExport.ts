import { useMemo } from 'react';
import { useGetFindingsQuery } from '../../../api/generated';
import { useUrlSearch } from '../../../url/useUrlSearch';
import { DEFAULT_FILTERS, exportUrl, parseFilters, toQueryArg } from './findingsUrl';

export type ReportExportState = {
  href: string;
  /** Total of the current findings list; undefined off the findings page, while loading or after an error. */
  total: number | undefined;
  /** 'list': the findings page's current filters; 'all': default filters (another page is shown). */
  scope: 'list' | 'all';
};

// The header's report export. On the findings page the filters come from the URL, parsed like the list
// does, and the list query is read with the same arguments, so RTK Query shares the cached request (no
// second fetch) and the header knows the total. On any other page: the default filters, no request.
export function useReportExport(onFindingsPage: boolean): ReportExportState {
  const [search] = useUrlSearch();
  const filters = useMemo(() => (onFindingsPage ? parseFilters(search) : DEFAULT_FILTERS), [onFindingsPage, search]);
  const { data, isError } = useGetFindingsQuery(toQueryArg(filters), { skip: !onFindingsPage });
  return {
    href: exportUrl(filters),
    total: onFindingsPage && !isError ? data?.total : undefined,
    scope: onFindingsPage ? 'list' : 'all',
  };
}
