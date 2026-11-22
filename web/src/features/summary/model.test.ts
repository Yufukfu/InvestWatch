import { describe, expect, it } from 'vitest';
import { formatDay } from './model';

describe('formatDay', () => {
  it('writes day.month.year with two-digit day and month', () => {
    expect(formatDay(new Date(2026, 0, 5))).toBe('05.01.2026');
    expect(formatDay(new Date(2026, 10, 22))).toBe('22.11.2026');
  });
});
