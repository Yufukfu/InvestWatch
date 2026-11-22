import { useMemo } from 'react';
import { useGetFindingsQuery, type Finding, type GetFindingsApiArg } from '../../../api/generated';
import { aggregateAdvertisers } from '../aggregate';
import { MAX_PAGES, PAGE_SIZE, type AdvertiserFinding, type AdvertisersView } from '../model';

// The generated DTO stops here (ADR 0204).
function toAdvertiserFinding(f: Finding): AdvertiserFinding {
  return {
    id: f.id,
    module: f.module,
    advertiser: f.advertiser && {
      name: f.advertiser.name,
      handle: f.advertiser.handle,
      profileUrl: f.advertiser.profile_url,
      website: f.advertiser.website,
    },
    firm: f.firm && { name: f.firm.name, registryId: f.firm.registry_id },
    title: f.title,
    platform: f.platform,
    score: f.score,
    riskLevel: f.risk_level ?? undefined,
    detectedAt: f.detected_at,
  };
}

const arg = (page: number): GetFindingsApiArg => ({ module: 'M1', sort: '-detected_at', page, pageSize: PAGE_SIZE });

// M1 findings, most recent first, in at most MAX_PAGES pages of PAGE_SIZE. Pages 2 and 3 are requested
// only when the first response's total needs them. A fixed number of hook calls (rules of hooks).
export function useAdvertisers(): AdvertisersView {
  const p1 = useGetFindingsQuery(arg(1));
  const pages = p1.data ? Math.min(MAX_PAGES, Math.ceil(p1.data.total / PAGE_SIZE)) : 1;
  const p2 = useGetFindingsQuery(arg(2), { skip: pages < 2 });
  const p3 = useGetFindingsQuery(arg(3), { skip: pages < 3 });
  const needed = [p1, p2, p3].slice(0, pages);
  const isError = needed.some((p) => p.isError);
  const complete = needed.every((p) => p.data);
  const data1 = p1.data;
  const data2 = pages >= 2 ? p2.data : undefined;
  const data3 = pages >= 3 ? p3.data : undefined;

  const items = useMemo(
    () => [data1, data2, data3].flatMap((d) => d?.items ?? []).map(toAdvertiserFinding),
    [data1, data2, data3],
  );
  const rows = useMemo(() => aggregateAdvertisers(items), [items]);
  // M1 only, deduped by id (a finding can move between pages while they load).
  const findings = useMemo(() => {
    const seen = new Set<string>();
    return items.filter((f) => f.module === 'M1' && !seen.has(f.id) && Boolean(seen.add(f.id)));
  }, [items]);

  return {
    rows: isError || !complete ? undefined : rows,
    findings: isError || !complete ? undefined : findings,
    loaded: isError || !complete ? 0 : items.length,
    total: isError ? undefined : data1?.total,
    isLoading: !isError && !complete,
    isError,
  };
}
