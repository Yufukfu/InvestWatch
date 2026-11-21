#!/usr/bin/env node
// Snapshots the shared contract (../contracts) into web/ so the web app builds and deploys on its own.
//  - bundles contracts/openapi.yaml (+ external schema refs) into src/api/openapi.json
//  - copies the REST mocks into src/mocks/fixtures/
// `--check` fails when the committed snapshot is out of date: a changed or extra file, or a
// src/api/generated.ts that no longer matches what the codegen produces from the snapshot.
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import SwaggerParser from '@apidevtools/swagger-parser';
import { generateEndpoints } from '@rtk-query/codegen-openapi';

// IW_WEB_DIR / IW_CONTRACTS_DIR override target and source, so tests run against temp copies.
const webDir = process.env.IW_WEB_DIR ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
process.chdir(webDir);
const contractsDir = process.env.IW_CONTRACTS_DIR ?? path.resolve(webDir, '..', 'contracts');
const check = process.argv.includes('--check');
// Forward slashes on every OS, so messages (and tests) read the same on Windows.
const rel = (file) => path.relative(webDir, file).split(path.sep).join('/');

const outputs = new Map();

const bundled = await SwaggerParser.bundle(path.join(contractsDir, 'openapi.yaml'));
const openapiFile = path.join(webDir, 'src/api/openapi.json');
outputs.set(openapiFile, `${JSON.stringify(bundled, null, 2)}\n`);

const fixturesDir = path.join(webDir, 'src/mocks/fixtures');
for (const file of fs.readdirSync(path.join(contractsDir, 'mocks')).filter((f) => f.endsWith('.json'))) {
  outputs.set(path.join(fixturesDir, file), fs.readFileSync(path.join(contractsDir, 'mocks', file), 'utf8'));
}

const stale = [];
for (const [file, content] of outputs) {
  const current = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
  if (current === content) continue;
  if (check) {
    stale.push(rel(file));
  } else {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, content);
  }
}

// Fixtures whose source mock was removed from contracts/mocks.
if (fs.existsSync(fixturesDir)) {
  for (const file of fs.readdirSync(fixturesDir).map((f) => path.join(fixturesDir, f))) {
    if (outputs.has(file)) continue;
    if (check) stale.push(rel(file));
    else fs.rmSync(file);
  }
}

// The generated client must match the snapshot (catches "synced but forgot api:generate").
if (check && stale.length === 0) {
  const config = createRequire(import.meta.url)(path.join(webDir, 'openapi-config.cjs'));
  const generatedFile = path.join(webDir, config.outputFile);
  // Generate next to the real file so relative imports match, then compare and remove it.
  const probe = path.join(path.dirname(generatedFile), '.generated.check.ts');
  let expected;
  try {
    await generateEndpoints({
      ...config,
      // Paths relative to web/ (as the CLI resolves them), so the generated import is "./baseApi".
      schemaFile: rel(openapiFile),
      outputFile: rel(probe),
    });
    expected = fs.readFileSync(probe, 'utf8');
  } finally {
    fs.rmSync(probe, { force: true });
  }
  const current = fs.existsSync(generatedFile) ? fs.readFileSync(generatedFile, 'utf8') : null;
  if (current !== expected) stale.push(rel(generatedFile));
}

if (stale.length) {
  process.stderr.write(`Contract snapshot is stale, run "npm run api:generate":\n  ${stale.join('\n  ')}\n`);
  process.exit(1);
}
process.stdout.write(check ? 'Contract snapshot is up to date.\n' : `Synced ${outputs.size} contract files.\n`);
