import { describe, expect, it } from 'vitest';
import { aggregateAdvertisers } from './aggregate';
import { buildGraph, EDGE_MAX, EDGE_MIN, edgeWidth } from './graph';
import type { AdvertiserFinding } from './model';

let n = 0;
function f(handle: string, firm: string | null): AdvertiserFinding {
  n += 1;
  return { id: `g-${n}`, module: 'M1', advertiser: { handle }, firm: firm ? { name: firm, registryId: `r-${firm}` } : null };
}
const times = (k: number, handle: string, firm: string | null) => Array.from({ length: k }, () => f(handle, firm));

describe('edgeWidth', () => {
  it('maps the largest count to the maximum width and grows with the count', () => {
    expect(edgeWidth(10, 10)).toBe(EDGE_MAX);
    expect(edgeWidth(1, 10)).toBeGreaterThanOrEqual(EDGE_MIN);
    expect(edgeWidth(1, 10)).toBeLessThan(edgeWidth(2, 10));
    expect(edgeWidth(5, 10)).toBeLessThan(edgeWidth(6, 10));
  });

  it('stays within bounds for odd input', () => {
    expect(edgeWidth(0, 0)).toBe(EDGE_MIN);
    expect(edgeWidth(20, 10)).toBe(EDGE_MAX);
  });
});

describe('buildGraph', () => {
  const rows = aggregateAdvertisers([
    ...times(3, '@a', 'X'),
    ...times(1, '@a', 'Y'),
    ...times(1, '@a', null),
    ...times(2, '@b', 'X'),
    ...times(2, '@c', null),
  ]);

  it('draws one edge per advertiser-firm pair with its count, skipping unmatched findings', () => {
    const g = buildGraph(rows);
    expect(g.edges.map((e) => [e.advertiser, e.firm, e.count, e.repeat])).toEqual([
      ['h:@a', 'r-X', 3, true],
      ['h:@a', 'r-Y', 1, true],
      ['h:@b', 'r-X', 2, false],
    ]);
    expect(g.edges[0].width).toBe(EDGE_MAX);
    expect(g.edges[1].width).toBeLessThan(g.edges[2].width);
  });

  it('lists advertisers with a matched firm and sums the firms over the drawn edges', () => {
    const g = buildGraph(rows);
    expect(g.advertisers.map((a) => [a.key, a.label, a.count, a.repeat])).toEqual([
      ['h:@a', '@a', 5, true],
      ['h:@b', '@b', 2, false],
    ]);
    // Both firms get most of their findings from the first advertiser; the larger firm comes first.
    expect(g.firms.map((x) => [x.key, x.name, x.count])).toEqual([
      ['r-X', 'X', 5],
      ['r-Y', 'Y', 1],
    ]);
    expect(g.unmatched).toBe(1);
    expect(g.hidden).toBe(0);
  });

  it("orders firms like hen68's mockup: each at the row of the advertiser that sends it the most findings", () => {
    // The placeholder data of the Powiązania mockup (issue #72).
    const mockup = aggregateAdvertisers([
      ...times(5, '@finanse_z_pasja', 'OKX'), ...times(3, '@finanse_z_pasja', 'Nordic'), ...times(1, '@finanse_z_pasja', 'Capital'),
      ...times(4, '@kdpwiadomosci', 'OKX'), ...times(3, '@kdpwiadomosci', 'Capital'),
      ...times(4, '@krypto_mentor_pl', 'Nordic'), ...times(2, '@krypto_mentor_pl', 'Bitvest'),
      ...times(4, '@zysk_codziennie', 'Bitvest'),
      ...times(3, '@inwestuj_z_tomkiem', 'OKX'),
      ...times(2, '@forex_sygnaly24', 'Alpha'),
      ...times(1, '@mama_na_gieldzie', 'Alpha'),
    ]);
    const g = buildGraph(mockup);
    expect(g.advertisers.map((a) => a.label)).toEqual(['@finanse_z_pasja', '@kdpwiadomosci', '@krypto_mentor_pl', '@zysk_codziennie', '@inwestuj_z_tomkiem', '@forex_sygnaly24', '@mama_na_gieldzie']);
    expect(g.firms.map((x) => [x.name, x.count])).toEqual([['OKX', 12], ['Capital', 4], ['Nordic', 7], ['Bitvest', 6], ['Alpha', 3]]);
  });

  it('places nodes top to bottom inside the height and keeps the edge ends on them', () => {
    const g = buildGraph(rows);
    expect(g.advertisers[0].y).toBeLessThan(g.advertisers[1].y);
    for (const node of [...g.advertisers, ...g.firms]) {
      expect(node.y).toBeGreaterThan(0);
      expect(node.y).toBeLessThan(g.height);
    }
    const e = g.edges[0];
    expect(e.y1).toBe(g.advertisers[0].y);
    expect(e.y2).toBe(g.firms.find((x) => x.key === e.firm)?.y);
  });

  it('shows at most the given number of advertisers and reports the rest as hidden', () => {
    const many = aggregateAdvertisers(['@1', '@2', '@3', '@4'].flatMap((h, i) => times(4 - i, h, 'X')));
    const g = buildGraph(many, 2);
    expect(g.advertisers.map((a) => a.label)).toEqual(['@1', '@2']);
    expect(g.hidden).toBe(2);
    expect(g.firms[0].count).toBe(7);
  });
});
