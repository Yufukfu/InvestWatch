import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FILTERS,
  hasTriageFlag,
  parseFilters,
  parseSelected,
  serializeUrl,
  toQueryArg,
  triageUrl,
  withFilter,
} from './findingsUrl';

describe('parseFilters', () => {
  it('returns the defaults for an empty search', () => {
    expect(parseFilters('')).toEqual(DEFAULT_FILTERS);
  });

  it('reads every valid parameter', () => {
    const f = parseFilters(
      '?module=M1&status=new,in_review&risk_level=high&platform=instagram&score_min=0.4&date_from=2026-11-20&date_to=2026-11-21&q=jan&sort=-score&page=2&page_size=10',
    );
    expect(f).toEqual({
      module: 'M1',
      status: ['new', 'in_review'],
      riskLevel: 'high',
      platform: 'instagram',
      scoreMin: 0.4,
      dateFrom: '2026-11-20',
      dateTo: '2026-11-21',
      q: 'jan',
      sort: '-score',
      page: 2,
      pageSize: 10,
    });
  });

  it('drops invalid values and keeps the defaults', () => {
    const f = parseFilters(
      '?module=M9&status=new,approved&risk_level=extreme&platform=myspace&score_min=1.5&date_from=yesterday&sort=title&page=0&page_size=7',
    );
    expect(f).toEqual({ ...DEFAULT_FILTERS, status: ['new'] });
  });

  it('rejects a negative score, a fractional page and an empty query', () => {
    expect(parseFilters('?score_min=-0.1&page=1.5&q=').scoreMin).toBeUndefined();
    expect(parseFilters('?page=1.5').page).toBe(1);
    expect(parseFilters('?q=%20%20').q).toBeUndefined();
  });

  it('accepts score_min at both bounds', () => {
    expect(parseFilters('?score_min=0').scoreMin).toBe(0);
    expect(parseFilters('?score_min=1').scoreMin).toBe(1);
  });
});

describe('parseSelected', () => {
  it('reads a uuid and ignores anything else', () => {
    expect(parseSelected('?finding=94f686c6-70c3-5ec9-9b6f-c97032c380c6')).toBe('94f686c6-70c3-5ec9-9b6f-c97032c380c6');
    expect(parseSelected('?finding=../../etc')).toBeUndefined();
    expect(parseSelected('')).toBeUndefined();
  });
});

describe('serializeUrl', () => {
  it('omits defaults, so the plain view has a clean URL', () => {
    expect(serializeUrl(DEFAULT_FILTERS, undefined)).toBe('');
  });

  it('round-trips through parseFilters', () => {
    const f = { ...DEFAULT_FILTERS, module: 'M3' as const, status: ['confirmed' as const], sort: 'score' as const, page: 3, q: 'a b' };
    const s = serializeUrl(f, '94f686c6-70c3-5ec9-9b6f-c97032c380c6');
    expect(parseFilters(s)).toEqual(f);
    expect(parseSelected(s)).toBe('94f686c6-70c3-5ec9-9b6f-c97032c380c6');
  });
});

describe('withFilter', () => {
  it('resets the page to 1 when a filter changes', () => {
    const f = { ...DEFAULT_FILTERS, page: 4 };
    expect(withFilter(f, { riskLevel: 'low' })).toEqual({ ...DEFAULT_FILTERS, riskLevel: 'low', page: 1 });
  });

  it('keeps an explicit page change', () => {
    expect(withFilter(DEFAULT_FILTERS, { page: 2 }).page).toBe(2);
  });
});

describe('toQueryArg', () => {
  it('maps filters to the generated query arguments, with whole-day UTC bounds', () => {
    const arg = toQueryArg({
      ...DEFAULT_FILTERS,
      status: ['new', 'closed'],
      dateFrom: '2026-11-20',
      dateTo: '2026-11-21',
      scoreMin: 0.5,
    });
    expect(arg).toEqual({
      status: 'new,closed',
      dateFrom: '2026-11-20T00:00:00Z',
      dateTo: '2026-11-21T23:59:59Z',
      scoreMin: 0.5,
      sort: '-detected_at',
      page: 1,
      pageSize: 25,
    });
  });

  it('sends no empty parameters', () => {
    expect(toQueryArg(DEFAULT_FILTERS)).toEqual({ sort: '-detected_at', page: 1, pageSize: 25 });
  });

describe('serialised parameter names (shared links)', () => {
  it('writes every filter under its GET /findings name, in a fixed order', () => {
    const s = serializeUrl(
      {
        module: 'M1',
        status: ['new', 'in_review'],
        riskLevel: 'high',
        platform: 'instagram',
        scoreMin: 0.4,
        dateFrom: '2026-11-20',
        dateTo: '2026-11-21',
        q: 'jan k',
        sort: '-score',
        page: 2,
        pageSize: 10,
      },
      '94f686c6-70c3-5ec9-9b6f-c97032c380c6',
    );
    expect(s).toBe(
      '?module=M1&status=new,in_review&risk_level=high&platform=instagram&score_min=0.4&date_from=2026-11-20&date_to=2026-11-21&q=jan+k&sort=-score&page=2&page_size=10&finding=94f686c6-70c3-5ec9-9b6f-c97032c380c6',
    );
  });

  it('sends platform, q and page size to the backend', () => {
    expect(toQueryArg({ ...DEFAULT_FILTERS, platform: 'tiktok', q: 'kurs', pageSize: 50 })).toEqual({
      platform: 'tiktok',
      q: 'kurs',
      sort: '-detected_at',
      page: 1,
      pageSize: 50,
    });
  });
});

describe('triage URL', () => {
  it('asks for new high-risk findings on page 1 and carries a one-shot flag', () => {
    expect(triageUrl()).toBe('?status=new&risk_level=high&triage=1');
  });

  it('reads the flag only when it is exactly 1', () => {
    expect(hasTriageFlag('?status=new&risk_level=high&triage=1')).toBe(true);
    expect(hasTriageFlag('?triage=0')).toBe(false);
    expect(hasTriageFlag('?triage=')).toBe(false);
    expect(hasTriageFlag('?status=new')).toBe(false);
    expect(hasTriageFlag('')).toBe(false);
  });

  it('parses to the triage filters and drops the flag when the URL is serialized again', () => {
    const f = parseFilters(triageUrl());
    expect(f).toEqual({ ...DEFAULT_FILTERS, status: ['new'], riskLevel: 'high' });
    expect(serializeUrl(f, undefined)).toBe('?status=new&risk_level=high');
  });
});
});
