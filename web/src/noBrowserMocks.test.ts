/// <reference types="node" />
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// The running app always talks to the backend (the api, or contracts/mock-server); MSW is a Vitest-only fake.
const webRoot = resolve(import.meta.dirname, '..');
const srcRoot = join(webRoot, 'src');
const testSupport = join(srcRoot, 'test');

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const path = join(dir, e.name);
    return e.isDirectory() ? walk(path) : [path];
  });
}

const isTestFile = (f: string) => /\.test\.[jt]sx?$/.test(f);
const isCode = (f: string) => /\.[cm]?[jt]sx?$/.test(f);

// Everything the browser or the build can load: app sources, type declarations, public assets, config and the HTML entry.
const shipped = [
  ...walk(srcRoot).filter((f) => !f.startsWith(testSupport + '/') && !isTestFile(f)),
  ...walk(join(webRoot, 'public')),
  ...readdirSync(webRoot)
    .filter((n) => /\.(html|[cm]?[jt]s)$/.test(n) || n.startsWith('.env'))
    .map((n) => join(webRoot, n)),
];
const read = (f: string) => readFileSync(f, 'utf8');
const rel = (fs: string[]) => fs.map((f) => relative(webRoot, f));

describe('no in-browser fake backend', () => {
  it('shipped code never imports msw or registers a service worker', () => {
    const offenders = shipped.filter((f) => /['"]msw(\/|['"])|serviceWorker/.test(read(f)));
    expect(rel(offenders)).toEqual([]);
  });

  it('shipped code never imports the Vitest support folder (src/test)', () => {
    const offenders = shipped.filter(
      (f) => isCode(f) && /(from\s+|import\s*\(\s*|import\s+|require\s*\(\s*)['"][^'"]*\/test(\/[^'"]*)?['"]/.test(read(f)),
    );
    expect(rel(offenders)).toEqual([]);
  });

  it('no file in src, tests included, starts a browser MSW worker', () => {
    const offenders = walk(srcRoot).filter(
      (f) => f !== import.meta.filename && /msw\/browser|setupWorker/.test(read(f)),
    );
    expect(rel(offenders)).toEqual([]);
  });

  it('ships no mock service worker and no mock switch', () => {
    expect(existsSync(join(webRoot, 'public', 'mockServiceWorker.js'))).toBe(false);
    expect(existsSync(join(srcRoot, 'mocks'))).toBe(false);
    const offenders = shipped.filter((f) => /useMocks|VITE_USE_MOCKS/.test(read(f)));
    expect(rel(offenders)).toEqual([]);
  });
});
