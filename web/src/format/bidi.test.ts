import { describe, expect, it } from 'vitest';
import { isolate } from './bidi';

const FSI = '\u2068';
const PDI = '\u2069';
const LRI = '\u2066';
const RLI = '\u2067';
const RLO = '\u202E';

describe('isolate', () => {
  it('wraps the text in FSI and PDI and keeps it otherwise unchanged', () => {
    expect(isolate('Płatne sygnały')).toBe(`${FSI}Płatne sygnały${PDI}`);
    expect(isolate(`Zysk ${RLO}gpj.exe <img src=x>`)).toBe(`${FSI}Zysk ${RLO}gpj.exe <img src=x>${PDI}`);
    expect(isolate('')).toBe(`${FSI}${PDI}`);
  });

  it('keeps isolates the text opens and closes itself', () => {
    expect(isolate(`a${RLI}b${PDI}c`)).toBe(`${FSI}a${RLI}b${PDI}c${PDI}`);
  });

  it('drops a PDI with no opener, so the text cannot close the outer isolate early', () => {
    expect(isolate(`a${PDI}${RLO}b`)).toBe(`${FSI}a${RLO}b${PDI}`);
    expect(isolate(`${RLI}a${PDI}${PDI}b`)).toBe(`${FSI}${RLI}a${PDI}b${PDI}`);
  });

  it('closes isolates the text leaves open, so the outer PDI matches the outer FSI', () => {
    expect(isolate(`a${RLI}b`)).toBe(`${FSI}a${RLI}b${PDI}${PDI}`);
    expect(isolate(`${LRI}${FSI}a`)).toBe(`${FSI}${LRI}${FSI}a${PDI}${PDI}${PDI}`);
  });

  it('turns a paragraph separator into a space, so the isolate spans the whole text', () => {
    expect(isolate(`a\nb\r\nc\u2029d\u0085e\u001Cf\u001Dg\u001Eh`)).toBe(`${FSI}a b  c d e f g h${PDI}`);
  });
});
