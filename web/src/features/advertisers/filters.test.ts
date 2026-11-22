import { describe, expect, it } from 'vitest';
import { aggregateAdvertisers } from './aggregate';
import { DEFAULT_ADVERTISER_FILTERS, filterFindings, filterRows, kpis } from './filters';
import type { AdvertiserFinding } from './model';

const NOW = Date.parse('2026-11-22T12:00:00Z');
let n = 0;
function f(handle: string, firm: string | null, extra: Partial<AdvertiserFinding> = {}): AdvertiserFinding {
  n += 1;
  return {
    id: `id-${n}`,
    module: 'M1',
    advertiser: { handle },
    firm: firm ? { name: firm, registryId: `r-${firm}` } : null,
    riskLevel: 'high',
    detectedAt: '2026-11-22T10:00:00Z',
    ...extra,
  };
}

describe('filterFindings', () => {
  it('keeps the last 30 days with the default filters, as in the mockup', () => {
    const recent = f('@b', null, { riskLevel: undefined });
    const old = f('@a', 'X', { detectedAt: '2020-01-01T00:00:00Z' });
    expect(DEFAULT_ADVERTISER_FILTERS.period).toBe('30');
    expect(filterFindings([old, recent], DEFAULT_ADVERTISER_FILTERS, NOW)).toEqual([recent]);
  });

  it('keeps findings detected within the period, boundary included', () => {
    const inside = f('@a', 'X', { detectedAt: '2026-11-15T12:00:00Z' });
    const outside = f('@a', 'X', { detectedAt: '2026-11-15T11:59:59Z' });
    const bad = f('@a', 'X', { detectedAt: 'not a date' });
    expect(filterFindings([inside, outside, bad], { ...DEFAULT_ADVERTISER_FILTERS, period: '7' }, NOW)).toEqual([inside]);
    expect(filterFindings([inside, outside], { ...DEFAULT_ADVERTISER_FILTERS, period: '30' }, NOW)).toEqual([inside, outside]);
  });

  it('keeps only the chosen risk level', () => {
    const high = f('@a', 'X');
    const low = f('@a', 'X', { riskLevel: 'low' });
    const none = f('@a', 'X', { riskLevel: undefined });
    expect(filterFindings([high, low, none], { ...DEFAULT_ADVERTISER_FILTERS, risk: 'low' }, NOW)).toEqual([low]);
  });
});

describe('filterRows', () => {
  const rows = aggregateAdvertisers([f('@a', 'X'), f('@a', 'Y'), f('@b', 'X'), f('@b', 'X'), f('@c', 'X')]);

  it('drops advertisers below the minimum number of findings', () => {
    expect(filterRows(rows, { ...DEFAULT_ADVERTISER_FILTERS, minFindings: 2 }).map((r) => r.handle)).toEqual(['@a', '@b']);
    expect(filterRows(rows, { ...DEFAULT_ADVERTISER_FILTERS, minFindings: 1 }).map((r) => r.handle)).toEqual(['@a', '@b', '@c']);
  });

  it('keeps only repeat advertisers when asked', () => {
    expect(filterRows(rows, { ...DEFAULT_ADVERTISER_FILTERS, repeatOnly: true }).map((r) => r.handle)).toEqual(['@a']);
  });
});

describe('kpis', () => {
  it('counts advertisers that promote a matched firm, distinct matched firms, repeat advertisers and matched findings', () => {
    // @c has no matched firm: it promotes no licensed firm, so the sentence does not count it.
    const rows = aggregateAdvertisers([f('@a', 'X'), f('@a', 'Y'), f('@b', 'X'), f('@b', null), f('@c', null)]);
    expect(kpis(rows)).toEqual({ advertisers: 2, firms: 2, repeat: 1, matchedFindings: 3 });
  });

  it('is all zeros for no rows', () => {
    expect(kpis([])).toEqual({ advertisers: 0, firms: 0, repeat: 0, matchedFindings: 0 });
  });
});
