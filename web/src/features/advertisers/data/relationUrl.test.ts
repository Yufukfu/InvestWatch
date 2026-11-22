import { describe, expect, it } from 'vitest';
import { findingSearch, parseRelation, relationSearch } from './relationUrl';

describe('relation URL state', () => {
  it('round-trips an advertiser and firm, keeping other parameters', () => {
    const search = relationSearch('?module=M2', { advertiser: 'h:@finanse z&pasja', firm: 'name:okx europe' });
    expect(new URLSearchParams(search).get('module')).toBe('M2');
    expect(parseRelation(search)).toEqual({ advertiser: 'h:@finanse z&pasja', firm: 'name:okx europe' });
  });

  it('round-trips an advertiser without a firm (the whole profile)', () => {
    expect(parseRelation(relationSearch('', { advertiser: 'p:https://x/y' }))).toEqual({ advertiser: 'p:https://x/y' });
  });

  it('closing the relation drops both parameters and nothing else', () => {
    const open = relationSearch('?q=x', { advertiser: 'h:@a', firm: 'rx' });
    expect(relationSearch(open, undefined)).toBe('?q=x');
    expect(relationSearch('?rel_adv=h%3A%40a', undefined)).toBe('');
  });

  it('ignores a missing or blank advertiser and a blank firm', () => {
    expect(parseRelation('')).toBeUndefined();
    expect(parseRelation('?rel_firm=rx')).toBeUndefined();
    expect(parseRelation('?rel_adv=%20')).toBeUndefined();
    expect(parseRelation('?rel_adv=h%3A%40a&rel_firm=')).toEqual({ advertiser: 'h:@a' });
  });

  it('opens a finding without the relation parameters', () => {
    const search = findingSearch('?rel_adv=h%3A%40a&rel_firm=rx&q=x', 'abc');
    const p = new URLSearchParams(search);
    expect(p.get('finding')).toBe('abc');
    expect(p.get('q')).toBe('x');
    expect(p.has('rel_adv')).toBe(false);
    expect(p.has('rel_firm')).toBe(false);
  });
});
