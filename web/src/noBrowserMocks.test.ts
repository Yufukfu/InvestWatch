/// <reference types="node" />
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// The running app always talks to the backend (the api, or contracts/mock-server); MSW is a Vitest-only fake.
const webRoot = resolve(import.meta.dirname, '..');
const srcRoot = join(webRoot, 'src');

function appSources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const path = join(dir, e.name);
    if (e.isDirectory()) return path === join(srcRoot, 'test') ? [] : appSources(path);
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [path] : [];
  });
}

describe('no in-browser fake backend', () => {
  it('app code (outside src/test and tests) never imports msw or registers a service worker', () => {
    const offenders = appSources(srcRoot)
      .filter((f) => /from ['"]msw|import\(['"]msw|serviceWorker/.test(readFileSync(f, 'utf8')))
      .map((f) => relative(webRoot, f));
    expect(offenders).toEqual([]);
  });

  it('ships no mock service worker and no mock switch', () => {
    expect(existsSync(join(webRoot, 'public', 'mockServiceWorker.js'))).toBe(false);
    expect(existsSync(join(srcRoot, 'mocks'))).toBe(false);
    expect(readFileSync(join(srcRoot, 'config.ts'), 'utf8')).not.toMatch(/useMocks|VITE_USE_MOCKS/);
  });
});
