'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { evaluate } = require('./git-guard.js');

const deps = (over = {}) => ({
  branch: () => 'scraper/v1',
  headIsPushed: () => false,
  staged: () => [],
  activeChanges: () => ['scraper-v1'],
  now: () => new Date('2026-11-21T13:00:00+01:00'),
  ...over,
});

test('denies force push', () => {
  assert.match(evaluate('git push --force origin scraper/v1', deps()), /force push/);
  assert.match(evaluate('git push -f', deps()), /force push/);
  assert.match(evaluate('git push origin +scraper/v1', deps()), /force push/);
});

test('denies push to main, explicit or implicit', () => {
  assert.match(evaluate('git push origin main', deps()), /push to main/);
  assert.match(evaluate('git push', deps({ branch: () => 'main' })), /push while on main/);
});

test('denies pushing HEAD or a full ref to main', () => {
  assert.match(evaluate('git push origin HEAD', deps({ branch: () => 'main' })), /push to main/);
  assert.match(evaluate('git push origin HEAD:refs/heads/main', deps()), /push to main/);
  assert.match(evaluate('git push origin HEAD:main', deps()), /push to main/);
  assert.match(evaluate('git push origin refs/heads/main', deps()), /push to main/);
});

test('allows pushing HEAD or a named ref from a feature branch', () => {
  assert.equal(evaluate('git push origin HEAD', deps()), null);
  assert.equal(evaluate('git push origin HEAD:scraper/v1', deps()), null);
});

test('denies pushing every branch', () => {
  assert.match(evaluate('git push --all origin', deps()), /every branch/);
  assert.match(evaluate('git push --mirror origin', deps()), /every branch/);
});

test('denies git add chained before git commit, because the staged diff is not visible yet', () => {
  assert.match(evaluate('git add scraper/.env && git commit -m x', deps()), /separate call/);
  assert.match(evaluate('git add -A; git commit -m x', deps()), /separate call/);
  assert.equal(evaluate('git add -A', deps()), null);
  assert.equal(evaluate('git commit -m x', deps()), null);
});

test('allows plain push of a feature branch', () => {
  assert.equal(evaluate('git push -u origin scraper/v1', deps()), null);
});

test('denies reset --hard and whole-tree checkout but allows restore --staged', () => {
  assert.match(evaluate('git reset --hard HEAD~1', deps()), /reset --hard/);
  assert.match(evaluate('git checkout .', deps()), /whole tree/);
  assert.equal(evaluate('git restore --staged .', deps()), null);
});

test('denies amending only a pushed commit', () => {
  assert.match(evaluate('git commit --amend --no-edit', deps({ headIsPushed: () => true })), /amending a pushed/);
  assert.equal(evaluate('git commit --amend --no-edit', deps()), null);
});

test('a commit message that merely mentions force push is not blocked', () => {
  assert.equal(evaluate('git commit -m "docs: never git push --force"', deps()), null);
});

test('IW_ALLOW_GIT=1 lets a destructive command through', () => {
  assert.equal(evaluate('IW_ALLOW_GIT=1 git reset --hard', deps()), null);
});

test('denies staged .env but allows .env.example', () => {
  const bad = deps({ staged: () => [{ file: 'scraper/.env', added: ['KEY=x'] }] });
  assert.match(evaluate('git commit -m x', bad), /\.env is staged/);
  const ok = deps({ staged: () => [{ file: '.env.example', added: ['KEY='] }] });
  assert.equal(evaluate('git commit -m x', ok), null);
});

test('denies console.log in code, allows it in tests', () => {
  const code = deps({ staged: () => [{ file: 'web/src/a.ts', added: ['console.log(x)'] }] });
  assert.match(evaluate('git commit -m x', code), /console\.log/);
  const spec = deps({ staged: () => [{ file: 'web/src/a.test.ts', added: ['console.log(x)'] }] });
  assert.equal(evaluate('git commit -m x', spec), null);
});

test('service code needs an active OpenSpec change, unless skipped or spec is staged', () => {
  const staged = [{ file: 'scraper/app/main.py', added: ['x = 1'] }];
  const none = deps({ staged: () => staged, activeChanges: () => [] });
  assert.match(evaluate('git commit -m x', none), /no OpenSpec change/);
  assert.equal(evaluate('IW_SKIP_SPEC=1 git commit -m x', none), null);
  const withSpec = deps({
    staged: () => [...staged, { file: 'openspec/changes/scraper-v1/tasks.md', added: ['- [x] a'] }],
    activeChanges: () => [],
  });
  assert.equal(evaluate('git commit -m x', withSpec), null);
});

test('markdown inside a service directory needs no spec', () => {
  const d = deps({ staged: () => [{ file: 'scraper/CLAUDE.md', added: ['x'] }], activeChanges: () => [] });
  assert.equal(evaluate('git commit -m x', d), null);
});

test('docs-only commits need no spec', () => {
  const d = deps({ staged: () => [{ file: '.docs/ai-workflow.md', added: ['x'] }], activeChanges: () => [] });
  assert.equal(evaluate('git commit -m x', d), null);
});

const AFTER_FREEZE = () => new Date('2026-11-21T14:31:00+01:00');
const schemaEdit = [{ file: 'contracts/schemas/finding.schema.json', added: ['{}'] }];

test('contract files are editable before the Sat 14:30 freeze', () => {
  assert.equal(evaluate('git commit -m x', deps({ staged: () => schemaEdit })), null);
});

test('denies a contract change after the freeze, unless IW_CONTRACT_CHANGE=1', () => {
  const d = deps({ staged: () => schemaEdit, now: AFTER_FREEZE });
  assert.match(evaluate('git commit -m x', d), /contracts are frozen/);
  assert.equal(evaluate('IW_CONTRACT_CHANGE=1 git commit -m x', d), null);
});

test('the freeze starts exactly at 14:30', () => {
  const at = (t) => deps({ staged: () => schemaEdit, now: () => new Date(t) });
  assert.equal(evaluate('git commit -m x', at('2026-11-21T14:29:59+01:00')), null);
  assert.match(evaluate('git commit -m x', at('2026-11-21T14:30:00+01:00')), /contracts are frozen/);
});

test('markdown under contracts/ and other directories are unaffected by the freeze', () => {
  const doc = deps({ staged: () => [{ file: 'contracts/README.md', added: ['x'] }], now: AFTER_FREEZE });
  assert.equal(evaluate('git commit -m x', doc), null);
  const other = deps({ staged: () => [{ file: 'scraper/app/a.py', added: ['x'] }], now: AFTER_FREEZE });
  assert.equal(evaluate('git commit -m x', other), null);
});

test('non-git commands are ignored', () => {
  assert.equal(evaluate('ls -la', deps()), null);
});
