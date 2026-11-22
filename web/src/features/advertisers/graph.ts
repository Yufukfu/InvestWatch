import { advertiserLabel } from './aggregate';
import { NO_FIRM, type AdvertiserRow } from './model';

// Layout of the advertiser -> firm graph (inline SVG, no chart dependency). Pure: rows in, positions out.
export const EDGE_MIN = 1.5;
export const EDGE_MAX = 9;
export const ROW_HEIGHT = 62;
// Width of the edge area between the two label columns, in CSS pixels (the SVG is drawn 1:1, no stretching).
export const EDGE_AREA_WIDTH = 300;
export const GRAPH_MAX_ADVERTISERS = 12;

// Line thickness grows linearly with the number of findings of the pair; the largest pair gets EDGE_MAX.
export function edgeWidth(count: number, maxCount: number): number {
  if (maxCount <= 0 || count <= 0) return EDGE_MIN;
  const share = Math.min(1, count / maxCount);
  return Math.round((EDGE_MIN + (EDGE_MAX - EDGE_MIN) * share) * 100) / 100;
}

export type GraphAdvertiser = { key: string; label: string; count: number; repeat: boolean; y: number };
export type GraphFirm = { key: string; name: string; count: number; y: number };
export type GraphEdge = { advertiser: string; firm: string; count: number; repeat: boolean; width: number; y1: number; y2: number };
export type Graph = {
  advertisers: GraphAdvertiser[];
  firms: GraphFirm[];
  edges: GraphEdge[];
  height: number;
  // Advertisers left out: `hidden` over the cap, `unmatched` with no matched firm (both are in the table view).
  hidden: number;
  unmatched: number;
};

// Rows come sorted by count (aggregateAdvertisers). Firms are ordered by the mean position of the advertisers
// that promote them (fewer crossings), then by count.
export function buildGraph(rows: readonly AdvertiserRow[], maxAdvertisers = GRAPH_MAX_ADVERTISERS): Graph {
  const matched = rows.filter((r) => r.firms.some((f) => f.key !== NO_FIRM));
  const shown = matched.slice(0, maxAdvertisers);
  const firmAcc = new Map<string, { name: string; count: number; weighted: number }>();
  const pairs: Array<Omit<GraphEdge, 'width' | 'y1' | 'y2'>> = [];
  shown.forEach((r, i) => {
    for (const f of r.firms) {
      if (f.key === NO_FIRM || !f.name) continue;
      pairs.push({ advertiser: r.key, firm: f.key, count: f.count, repeat: r.repeat });
      const acc = firmAcc.get(f.key) ?? { name: f.name, count: 0, weighted: 0 };
      acc.count += f.count;
      acc.weighted += f.count * i;
      firmAcc.set(f.key, acc);
    }
  });
  const firmList = [...firmAcc.entries()]
    .map(([key, a]) => ({ key, name: a.name, count: a.count, center: a.weighted / a.count }))
    .sort((a, b) => a.center - b.center || b.count - a.count || a.name.localeCompare(b.name, 'pl'));
  const height = Math.max(shown.length, firmList.length, 1) * ROW_HEIGHT;
  const advStep = height / Math.max(shown.length, 1);
  const firmStep = height / Math.max(firmList.length, 1);
  const advertisers = shown.map((r, i) => ({ key: r.key, label: advertiserLabel(r), count: r.count, repeat: r.repeat, y: (i + 0.5) * advStep }));
  const firms = firmList.map((x, j) => ({ key: x.key, name: x.name, count: x.count, y: (j + 0.5) * firmStep }));
  const advY = new Map(advertisers.map((a) => [a.key, a.y]));
  const firmY = new Map(firms.map((x) => [x.key, x.y]));
  const maxCount = Math.max(0, ...pairs.map((p) => p.count));
  const edges = pairs.map((p) => ({
    ...p,
    width: edgeWidth(p.count, maxCount),
    y1: advY.get(p.advertiser) ?? 0,
    y2: firmY.get(p.firm) ?? 0,
  }));
  return { advertisers, firms, edges, height, hidden: matched.length - shown.length, unmatched: rows.length - matched.length };
}
