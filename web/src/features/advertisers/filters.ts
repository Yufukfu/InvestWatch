import { NO_FIRM, type AdvertiserFinding, type AdvertiserRow, type RiskLevel } from './model';

// Client-side filters of the Powiązania page. They narrow the M1 findings already loaded (at most
// FINDINGS_CAP); nothing is recomputed that the API owns (risk level is read, never derived).
export type AdvertiserPeriod = '7' | '30' | '90' | 'all';
export type AdvertiserFilters = {
  period: AdvertiserPeriod;
  risk: RiskLevel | 'all';
  minFindings: number;
  repeatOnly: boolean;
};

export const PERIODS: readonly AdvertiserPeriod[] = ['7', '30', '90', 'all'];
export const MIN_FINDINGS_OPTIONS: readonly number[] = [1, 2, 3, 5, 10];
export const DEFAULT_ADVERTISER_FILTERS: AdvertiserFilters = { period: 'all', risk: 'all', minFindings: 1, repeatOnly: false };

const DAY_MS = 24 * 60 * 60 * 1000;

// Period and risk level apply to findings, before grouping, so counts and the repeat rule follow them.
export function filterFindings(findings: readonly AdvertiserFinding[], filters: AdvertiserFilters, now: number): AdvertiserFinding[] {
  const from = filters.period === 'all' ? undefined : now - Number(filters.period) * DAY_MS;
  return findings.filter((f) => {
    if (filters.risk !== 'all' && f.riskLevel !== filters.risk) return false;
    if (from === undefined) return true;
    const t = Date.parse(f.detectedAt ?? '');
    return !Number.isNaN(t) && t >= from;
  });
}

// The minimum count and the repeat-only switch apply to the grouped advertisers.
export function filterRows(rows: readonly AdvertiserRow[], filters: AdvertiserFilters): AdvertiserRow[] {
  return rows.filter((r) => r.count >= filters.minFindings && (!filters.repeatOnly || r.repeat));
}

export type AdvertiserKpis = { advertisers: number; firms: number; repeat: number; matchedFindings: number };

export function kpis(rows: readonly AdvertiserRow[]): AdvertiserKpis {
  const firms = new Set<string>();
  let matchedFindings = 0;
  for (const r of rows)
    for (const f of r.firms) {
      if (f.key === NO_FIRM) continue;
      firms.add(f.key);
      matchedFindings += f.count;
    }
  // "N reklamodawców promuje M firm": an advertiser with no matched firm promotes no licensed firm.
  return { advertisers: rows.filter(hasMatchedFirm).length, firms: firms.size, repeat: rows.filter((r) => r.repeat).length, matchedFindings };
}

// True when the advertiser has at least one finding with a matched registry firm (an edge in the graph).
export function hasMatchedFirm(r: AdvertiserRow): boolean {
  return r.firms.some((f) => f.key !== NO_FIRM);
}
