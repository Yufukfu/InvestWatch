import { useGetStatsSummaryQuery } from '../../../api/generated';
import type { SummaryCounts } from '../model';

export function useSummary(): SummaryCounts | undefined {
  const { data } = useGetStatsSummaryQuery();
  if (!data) return undefined;
  return {
    total: data.total,
    highRisk: data.by_risk_level.high ?? 0,
    newCount: data.by_status.new ?? 0,
    byModule: Object.entries(data.by_module ?? {})
      .map(([module, count]) => ({ module, count: count ?? 0 }))
      .sort((a, b) => a.module.localeCompare(b.module)),
    m2Coverage: data.m2_coverage
      ? { total: data.m2_coverage.total, registryMatched: data.m2_coverage.registry_matched }
      : undefined,
  };
}
