import { describe, expect, it } from 'vitest';
import { aggregateAdvertisers } from './aggregate';
import type { AdvertiserFinding } from './model';

let n = 0;
function f(advertiser: AdvertiserFinding['advertiser'], firm?: AdvertiserFinding['firm'], extra: Partial<AdvertiserFinding> = {}): AdvertiserFinding {
  n += 1;
  return { id: `id-${n}`, module: 'M1', advertiser, firm, ...extra };
}
const X = { name: 'Firma X', registryId: 'rx' };
const Y = { name: 'Firma Y', registryId: 'ry' };

describe('aggregateAdvertisers', () => {
  it('groups by advertiser and firm, counts, and sorts by count', () => {
    const rows = aggregateAdvertisers([
      f({ name: 'B', handle: '@b' }, Y),
      f({ name: 'A', handle: '@a' }, X),
      f({ name: 'A', handle: '@A' }, Y),
      f({ name: 'A', handle: '@a' }, X),
    ]);
    expect(rows.map((r) => [r.handle, r.count])).toEqual([
      ['@a', 3],
      ['@b', 1],
    ]);
    expect(rows[0].firms).toEqual([
      { key: 'rx', name: 'Firma X', count: 2 },
      { key: 'ry', name: 'Firma Y', count: 1 },
    ]);
    expect(rows[0].name).toBe('A');
  });

  it('marks an advertiser as repeat from 2 findings, not at 1', () => {
    const rows = aggregateAdvertisers([f({ handle: '@a' }, X), f({ handle: '@a' }, X), f({ handle: '@b' }, X)]);
    expect(rows.map((r) => [r.handle, r.repeat])).toEqual([
      ['@a', true],
      ['@b', false],
    ]);
  });

  it('falls back to profile url, website, then name for the advertiser key', () => {
    const rows = aggregateAdvertisers([
      f({ name: 'P1', profileUrl: 'https://p/1' }, X),
      f({ name: 'P1 other name', profileUrl: 'https://p/1' }, X),
      f({ name: 'W1', website: 'https://w' }, X),
      f({ name: 'W2', website: 'https://w' }, X),
      f({ name: 'Only Name' }, X),
      f({ name: 'only name' }, X),
    ]);
    expect(rows.map((r) => r.count)).toEqual([2, 2, 2]);
  });

  it('keeps the profile url, else the website, as contact for an advertiser without name or handle', () => {
    const rows = aggregateAdvertisers([f({ profileUrl: 'https://p/9', website: 'https://w/9' }, X), f({ website: 'https://w/8' }, X), f({ handle: '@h' }, X)]);
    expect(rows.map((r) => r.contact)).toEqual([undefined, 'https://p/9', 'https://w/8']);
  });

  it('keys a firm by name when it has no registry id', () => {
    const rows = aggregateAdvertisers([f({ handle: '@a' }, { name: 'Firma Z' }), f({ handle: '@a' }, { name: 'firma z', registryId: null })]);
    expect(rows[0].firms).toEqual([{ key: 'name:firma z', name: 'Firma Z', count: 2 }]);
  });

  it('counts a finding without a firm under an unnamed firm entry', () => {
    const rows = aggregateAdvertisers([f({ handle: '@a' }, X), f({ handle: '@a' }, null), f({ handle: '@a' }, { name: '  ' })]);
    expect(rows[0].count).toBe(3);
    expect(rows[0].firms).toEqual([
      { key: 'none', name: undefined, count: 2 },
      { key: 'rx', name: 'Firma X', count: 1 },
    ]);
  });

  it('skips findings without an advertiser or without any advertiser identity', () => {
    const rows = aggregateAdvertisers([f(null, X), f(undefined, X), f({ name: '  ', handle: null }, X), f({ handle: '@a' }, X)]);
    expect(rows.map((r) => r.handle)).toEqual(['@a']);
  });

  it('ignores non-M1 findings and duplicate ids', () => {
    const dup = f({ handle: '@a' }, X);
    const rows = aggregateAdvertisers([dup, { ...dup }, f({ handle: '@a' }, X, { module: 'M3' })]);
    expect(rows).toHaveLength(1);
    expect(rows[0].count).toBe(1);
    expect(rows[0].repeat).toBe(false);
  });

  it('breaks count ties by name so the order is stable', () => {
    const rows = aggregateAdvertisers([f({ name: 'Zenon', handle: '@z' }, X), f({ name: 'Adam', handle: '@y' }, X)]);
    expect(rows.map((r) => r.name)).toEqual(['Adam', 'Zenon']);
  });
});
