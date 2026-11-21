import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseCodeowners, ownerOf, ownedDirs, loadCodeowners } from './lib/codeowners.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

const SAMPLE = `
# comment
*.md            @docs-team
analytics/      @Yufukfu
analytics/docs/ @hen68
/web/           @kacpermalczyk
**/fixtures/*.json @fixture-owner
`;

test('last matching pattern wins', () => {
  const rules = parseCodeowners(SAMPLE);
  assert.deepEqual(ownerOf(rules, 'analytics/src/x.py'), ['Yufukfu']);
  assert.deepEqual(ownerOf(rules, 'analytics/docs/a.md'), ['hen68']);
  // *.md comes first, so a later directory rule overrides it
  assert.deepEqual(ownerOf(rules, 'analytics/README.md'), ['Yufukfu']);
  assert.deepEqual(ownerOf(rules, 'README.md'), ['docs-team']);
});

test('a directory pattern matches below it and respects the segment boundary', () => {
  const rules = parseCodeowners(SAMPLE);
  assert.deepEqual(ownerOf(rules, 'web/src/app.ts'), ['kacpermalczyk']);
  assert.deepEqual(ownerOf(rules, 'web-old/src/app.ts'), []);
  assert.deepEqual(ownerOf(rules, 'web'), [], 'the directory pattern needs a path below it');
  // anchored `/web/` does not match a nested web directory
  assert.deepEqual(ownerOf(rules, 'scraper/web/x.ts'), []);
  // unanchored `analytics/`? it contains no inner slash, so it matches at any depth like GitHub does
  assert.deepEqual(ownerOf(rules, 'vendor/analytics/x.py'), ['Yufukfu']);
});

test('glob patterns: * stays in a segment, ** crosses segments', () => {
  const rules = parseCodeowners(SAMPLE);
  assert.deepEqual(ownerOf(rules, 'scraper/tests/fixtures/a.json'), ['fixture-owner']);
  assert.deepEqual(ownerOf(rules, 'fixtures/a.json'), ['fixture-owner']);
  assert.deepEqual(ownerOf(rules, 'scraper/tests/fixtures/deep/a.json'), []);
});

test('docs/* matches files directly in docs, not nested ones (GitHub semantics)', () => {
  const rules = parseCodeowners('/docs/* @a\n*.js @b\n');
  assert.deepEqual(ownerOf(rules, 'docs/x.md'), ['a']);
  assert.deepEqual(ownerOf(rules, 'docs/x/y.md'), []);
  assert.deepEqual(ownerOf(rules, 'src/deep/app.js'), ['b']);
});

test('a trailing comment cannot add an owner', () => {
  assert.deepEqual(ownerOf(parseCodeowners('/scraper/ @hen68 # @Yufukfu\n'), 'scraper/a.py'), ['hen68']);
});

test('loadCodeowners refuses a ref that git would read as an option', () => {
  assert.throws(() => loadCodeowners({ git: () => '', ref: '--output=/tmp/x' }), /ref/);
});

test('no match gives no owner', () => {
  assert.deepEqual(ownerOf(parseCodeowners('scraper/ @hen68\n'), 'api/main.py'), []);
});

test('unknown syntax fails closed instead of guessing', () => {
  for (const bad of ['!scraper/ @hen68', 'scraper/[ab] @hen68', 'scraper\\ x @hen68', 'scraper/', 'scraper/ hen68']) {
    assert.throws(() => parseCodeowners(bad), /CODEOWNERS line 1/, bad);
  }
});

test('ownedDirs lists the top-level directories a login owns', () => {
  const rules = parseCodeowners('scraper/ @hen68\n/web/ @kacpermalczyk\ninfra/ @kacpermalczyk\n');
  assert.deepEqual(ownedDirs(rules, 'kacpermalczyk'), ['web/', 'infra/']);
  assert.deepEqual(ownedDirs(rules, 'KacperMalczyk'), ['web/', 'infra/'], 'logins compare case-insensitively');
  assert.deepEqual(ownedDirs(rules, 'nobody'), []);
});

test('loadCodeowners reads the default-branch copy and returns null when it is missing', () => {
  const calls = [];
  const git = (args) => { calls.push(args); return 'scraper/ @hen68\n'; };
  const rules = loadCodeowners({ git, ref: 'origin/main' });
  assert.deepEqual(calls[0], ['show', 'origin/main:.github/CODEOWNERS']);
  assert.deepEqual(ownerOf(rules, 'scraper/x.py'), ['hen68']);
  const missing = loadCodeowners({ git: () => { throw new Error('fatal: path does not exist'); }, ref: 'origin/main' });
  assert.equal(missing, null);
});

test('the repository CODEOWNERS routes each module to its owner', () => {
  const rules = parseCodeowners(fs.readFileSync(path.join(ROOT, '.github/CODEOWNERS'), 'utf8'));
  assert.deepEqual(ownerOf(rules, 'scraper/collectors/x.py'), ['hen68']);
  assert.deepEqual(ownerOf(rules, 'web/src/App.tsx'), ['kacpermalczyk']);
  assert.deepEqual(ownerOf(rules, 'infra/compose.yaml'), [], 'infra/ is shared: no owner');
  for (const p of ['analytics/a.py', 'api/main.py', 'contracts/finding.schema.json']) {
    assert.deepEqual(ownerOf(rules, p), ['Yufukfu'], p);
  }
  assert.deepEqual(ownerOf(rules, '.docs/STATUS.md'), [], 'shared docs have no single owner');
});
