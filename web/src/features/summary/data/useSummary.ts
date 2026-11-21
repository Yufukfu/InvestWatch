import { useGetStatsSummaryQuery } from '../../../api/generated';
import type { SummaryCounts } from '../model';

export function useSummary(): SummaryCounts | undefined {
  const { data } = useGetStatsSummaryQuery();
  if (!data) return undefined;
  return {
    total: data.total,
    highRisk: data.by_risk_level.high ?? 0,
    newCount: data.by_status.new ?? 0,
  };
}
