import { describe, expect, it } from 'vitest';
import { plural } from './labels';

const p = (n: number) => plural(n, 'firma', 'firmy', 'firm');

describe('plural', () => {
  it('uses the Polish one, few and many forms, with 12-14 as many', () => {
    expect([1, 2, 3, 4, 5, 11, 12, 13, 14, 21, 22, 24, 25, 112, 122].map((n) => `${n} ${p(n)}`)).toEqual([
      '1 firma', '2 firmy', '3 firmy', '4 firmy', '5 firm', '11 firm', '12 firm', '13 firm', '14 firm',
      '21 firm', '22 firmy', '24 firmy', '25 firm', '112 firm', '122 firmy',
    ]);
    expect(p(0)).toBe('firm');
  });
});
