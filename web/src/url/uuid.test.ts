import { describe, expect, it } from 'vitest';
import { isUuid } from './uuid';

describe('isUuid', () => {
  it('accepts a UUID in either letter case', () => {
    expect(isUuid('94f686c6-70c3-5ec9-9b6f-c97032c380c6')).toBe(true);
    expect(isUuid('94F686C6-70C3-5EC9-9B6F-C97032C380C6')).toBe(true);
  });

  it('rejects text around the id, a wrong group length, a non-hex digit and a missing dash', () => {
    const id = '94f686c6-70c3-5ec9-9b6f-c97032c380c6';
    expect(isUuid(` ${id}`)).toBe(false);
    expect(isUuid(`${id} `)).toBe(false);
    expect(isUuid(`{${id}}`)).toBe(false);
    expect(isUuid(id.slice(1))).toBe(false);
    expect(isUuid(`${id}0`)).toBe(false);
    expect(isUuid(`g4f686c6-70c3-5ec9-9b6f-c97032c380c6`)).toBe(false);
    expect(isUuid(id.replace('-', ''))).toBe(false);
  });

  it('rejects values that are not strings', () => {
    expect(isUuid(undefined)).toBe(false);
    expect(isUuid(null)).toBe(false);
    expect(isUuid(42)).toBe(false);
    expect(isUuid({ id: '94f686c6-70c3-5ec9-9b6f-c97032c380c6' })).toBe(false);
  });
});
