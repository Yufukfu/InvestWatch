import { describe, expect, it } from 'vitest';
import { formatScore } from './score';

describe('formatScore', () => {
  it('uses a decimal comma and two places', () => {
    expect(formatScore(0.87)).toBe('0,87');
    expect(formatScore(0.5)).toBe('0,50');
    expect(formatScore(1)).toBe('1,00');
    expect(formatScore(0.456)).toBe('0,46');
  });
});
