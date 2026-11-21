import { useGetFindingsQuery, type Finding } from '../../../api/generated';
import type { FindingRow } from '../model';

// The generated DTO stops here. `module` and `status` are assigned from the generated unions, so a
// contract change that adds a value fails to compile in this file instead of leaking into components.
function toRow(f: Finding): FindingRow {
  return { id: f.id, module: f.module, title: f.title, platform: f.platform, score: f.score, status: f.status };
}

export function useFindings(): { rows: FindingRow[] | undefined; isLoading: boolean; isError: boolean } {
  const { data, isLoading, isError } = useGetFindingsQuery({ page: 1, pageSize: 50 });
  return { rows: data?.items.map(toRow), isLoading, isError };
}
