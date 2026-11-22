import { describe, expect, it } from 'vitest';
import { isolate } from './bidi';

describe('isolate', () => {
  it('wraps the value in FIRST STRONG ISOLATE and POP DIRECTIONAL ISOLATE', () => {
    expect(isolate('Płatne sygnały')).toBe('\u2068Płatne sygnały\u2069');
    expect(isolate('a\u202Eb')).toBe('\u2068a\u202Eb\u2069');
    expect(isolate('')).toBe('\u2068\u2069');
  });
});
