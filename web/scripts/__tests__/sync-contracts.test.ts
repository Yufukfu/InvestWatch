// @vitest-environment node
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

const webDir = path.resolve(__dirname, '..', '..');
const script = path.join(webDir, 'scripts', 'sync-contracts.mjs');
const contracts = path.resolve(webDir, '..', 'contracts');
const tmpDirs: string[] = [];

function check(contractsDir: string) {
  return spawnSync(process.execPath, [script, '--check'], {
    cwd: webDir,
    env: { ...process.env, IW_CONTRACTS_DIR: contractsDir },
    encoding: 'utf8',
  });
}

afterEach(() => {
  for (const dir of tmpDirs.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

describe('contracts:check', () => {
  it('passes when the snapshot matches contracts/', () => {
    const result = check(contracts);
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('up to date');
  });

  it('fails and names the file when a contract mock changed', () => {
    const copy = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-contracts-'));
    tmpDirs.push(copy);
    fs.cpSync(contracts, copy, { recursive: true });
    const mock = path.join(copy, 'mocks', 'health.json');
    fs.writeFileSync(mock, JSON.stringify({ status: 'degraded', services: {} }));

    const result = check(copy);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/mocks/fixtures/health.json');
  });

  it('fails when generated.ts no longer matches the snapshot', () => {
    const generated = path.join(webDir, 'src', 'api', 'generated.ts');
    const original = fs.readFileSync(generated, 'utf8');
    try {
      fs.writeFileSync(generated, original.replace('useGetHealthQuery,', ''));
      const result = check(contracts);
      expect(result.status).toBe(1);
      expect(result.stderr).toContain('src/api/generated.ts');
    } finally {
      fs.writeFileSync(generated, original);
    }
  });

  it('fails when a fixture has no source mock any more', () => {
    const extra = path.join(webDir, 'src', 'mocks', 'fixtures', 'removed-upstream.json');
    try {
      fs.writeFileSync(extra, '{}\n');
      const result = check(contracts);
      expect(result.status).toBe(1);
      expect(result.stderr).toContain('src/mocks/fixtures/removed-upstream.json');
    } finally {
      fs.rmSync(extra, { force: true });
    }
  });

  it('fails when the OpenAPI spec changed', () => {
    const copy = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-contracts-'));
    tmpDirs.push(copy);
    fs.cpSync(contracts, copy, { recursive: true });
    const spec = path.join(copy, 'openapi.yaml');
    fs.writeFileSync(spec, fs.readFileSync(spec, 'utf8').replace('version: 1.0.0', 'version: 1.0.1'));

    const result = check(copy);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/api/openapi.json');
  });
});
