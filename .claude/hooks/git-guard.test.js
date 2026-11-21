'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { evaluate } = require('./git-guard.js');

const deps = (over = {}) => ({
  branch: () => 'scraper/v1',
  headIsPushed: () => false,
  staged: () => [],
  activeChanges: () => ['scraper-v1'],
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
  const code = deps({ staged: () => [{ file: 'dashboard/src/a.ts', added: ['console.log(x)'] }] });
  assert.match(evaluate('git commit -m x', code), /console\.log/);
  const spec = deps({ staged: () => [{ file: 'dashboard/src/a.test.ts', added: ['console.log(x)'] }] });
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
  const d = deps({ staged: () => [{ file: 'doc/ai-workflow.md', added: ['x'] }], activeChanges: () => [] });
  assert.equal(evaluate('git commit -m x', d), null);
});

test('non-git commands are ignored', () => {
  assert.equal(evaluate('ls -la', deps()), null);
});
