// @vitest-environment node
// Every case runs the script against temp copies (IW_WEB_DIR, IW_CONTRACTS_DIR), never the real web/ files,
// so parallel test files never see a mutated generated.ts and an interrupted run leaves nothing behind.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

const realWeb = path.resolve(__dirname, '..', '..');
const realContracts = path.resolve(realWeb, '..', 'contracts');
const script = path.join(realWeb, 'scripts', 'sync-contracts.mjs');
const tmpDirs: string[] = [];

function tempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-sync-'));
  tmpDirs.push(dir);
  return dir;
}

/** A temp web/ with only what the script reads, and a temp contracts/. */
function sandbox() {
  const web = tempDir();
  fs.copyFileSync(path.join(realWeb, 'openapi-config.cjs'), path.join(web, 'openapi-config.cjs'));
  fs.cpSync(path.join(realWeb, 'src', 'api'), path.join(web, 'src', 'api'), { recursive: true });
  fs.cpSync(path.join(realWeb, 'src', 'test', 'fixtures'), path.join(web, 'src', 'test', 'fixtures'), {
    recursive: true,
  });
  const contracts = tempDir();
  fs.cpSync(realContracts, contracts, { recursive: true });
  return { web, contracts };
}

function check({ web, contracts }: { web: string; contracts: string }) {
  return spawnSync(process.execPath, [script, '--check'], {
    env: { ...process.env, IW_WEB_DIR: web, IW_CONTRACTS_DIR: contracts },
    encoding: 'utf8',
  });
}

afterEach(() => {
  for (const dir of tmpDirs.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

describe('contracts:check', () => {
  it('passes on the committed snapshot of contracts/', () => {
    const result = check({ web: realWeb, contracts: realContracts });
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('up to date');
  });

  it('fails and names the file when a contract mock changed', () => {
    const box = sandbox();
    fs.writeFileSync(path.join(box.contracts, 'mocks', 'health.json'), JSON.stringify({ status: 'degraded', services: {} }));
    const result = check(box);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/test/fixtures/health.json');
  });

  it('fails when generated.ts no longer matches the snapshot', () => {
    const box = sandbox();
    const generated = path.join(box.web, 'src', 'api', 'generated.ts');
    fs.writeFileSync(generated, fs.readFileSync(generated, 'utf8').replace('useGetHealthQuery,', ''));
    const result = check(box);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/api/generated.ts');
  });

  it('fails when a fixture has no source mock any more', () => {
    const box = sandbox();
    fs.writeFileSync(path.join(box.web, 'src', 'test', 'fixtures', 'removed-upstream.json'), '{}\n');
    const result = check(box);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/test/fixtures/removed-upstream.json');
  });

  it('fails when the OpenAPI spec changed', () => {
    const box = sandbox();
    const spec = path.join(box.contracts, 'openapi.yaml');
    fs.writeFileSync(spec, fs.readFileSync(spec, 'utf8').replace('version: 1.0.0', 'version: 1.0.1'));
    const result = check(box);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('src/api/openapi.json');
  });
});
