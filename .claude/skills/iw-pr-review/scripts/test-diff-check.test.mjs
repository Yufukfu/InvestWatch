// Run with: node --test ".claude/skills/iw-pr-review/scripts/*.test.mjs"
// Fixtures live in a disposable git repo, so the real InvestWatch tree is never read.

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkTestDiff, isTestFile } from './test-diff-check.mjs';

const sh = (cwd, ...args) => execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const roots = [];
after(() => roots.forEach((r) => fs.rmSync(r, { recursive: true, force: true })));

const OLD_PY = 'def test_a():\n    assert 1 == 1\n    assert 2 == 2\n';
const OLD_JS = "it('a', () => {\n  expect(1).toBe(1);\n  expect(2).toBe(2);\n});\n";

function write(root, files) {
  for (const [f, content] of Object.entries(files)) {
    const abs = path.join(root, f);
    if (content === null) fs.rmSync(abs);
    else {
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      fs.writeFileSync(abs, content);
    }
  }
}

function commit(root, files) {
  write(root, files);
  sh(root, 'add', '-A');
  sh(root, 'commit', '-q', '-m', 'change');
}

function makeRepo() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'test-diff-check-'));
  roots.push(root);
  sh(root, 'init', '-q', '-b', 'main');
  sh(root, 'config', 'user.email', 't@t');
  sh(root, 'config', 'user.name', 't');
  sh(root, 'config', 'commit.gpgsign', 'false');
  write(root, { 'scraper/tests/test_a.py': OLD_PY, 'web/src/a.test.js': OLD_JS, 'scraper/a.py': 'X = 1\n' });
  sh(root, 'add', '-A');
  sh(root, 'commit', '-q', '-m', 'init');
  sh(root, 'update-ref', 'refs/remotes/origin/main', 'HEAD');
  return root;
}

const run = (root, extra = {}) => checkTestDiff({ repoRoot: root, base: 'origin/main', head: 'HEAD', ...extra });
const kinds = (flags) => flags.map((f) => `${f.kind}:${f.file}`);

test('isTestFile matches pytest and JS test files only', () => {
  assert.equal(isTestFile('scraper/tests/test_a.py'), true);
  assert.equal(isTestFile('scraper/tests/conftest.py'), true);
  assert.equal(isTestFile('scraper/test_parser.py'), true);
  assert.equal(isTestFile('scraper/parser_test.py'), true);
  assert.equal(isTestFile('web/src/a.test.tsx'), true);
  assert.equal(isTestFile('web/src/__tests__/helper.js'), true);
  assert.equal(isTestFile('scraper/parser.py'), false);
  assert.equal(isTestFile('scraper/contest.py'), false);
  assert.equal(isTestFile('scraper/tests/fixtures/page.html'), false);
});

test('adding tests and assertions raises no flag', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': `${OLD_PY}\ndef test_b():\n    assert 3 == 3\n`, 'scraper/tests/test_b.py': 'def test_c():\n    assert True\n' });
  assert.deepEqual(run(root), []);
});

test('deleting a test file is flagged', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': null });
  assert.deepEqual(kinds(run(root)), ['deleted-test-file:scraper/tests/test_a.py']);
});

test('renaming a test file to a non-test name is flagged, to another test name is not', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': null, 'scraper/helper_a.py': OLD_PY });
  assert.deepEqual(kinds(run(root)), ['deleted-test-file:scraper/tests/test_a.py']);
  const ok = makeRepo();
  commit(ok, { 'scraper/tests/test_a.py': null, 'scraper/tests/test_renamed.py': OLD_PY });
  assert.deepEqual(run(ok), []);
});

test('an added skip, xfail or only marker is flagged (python and js)', () => {
  const cases = [
    ['scraper/tests/test_a.py', OLD_PY, '@pytest.mark.skip(reason="x")\ndef test_b():\n    assert 1\n'],
    ['scraper/tests/test_a.py', OLD_PY, '@pytest.mark.skipif(True, reason="x")\ndef test_b():\n    assert 1\n'],
    ['scraper/tests/test_a.py', OLD_PY, '@pytest.mark.xfail\ndef test_b():\n    assert 1\n'],
    ['scraper/tests/test_a.py', OLD_PY, 'def test_b():\n    pytest.skip("later")\n    assert 1\n'],
    ['web/src/a.test.js', OLD_JS, "it.skip('b', () => { expect(1).toBe(1); });\n"],
    ['web/src/a.test.js', OLD_JS, "it.only('b', () => { expect(1).toBe(1); });\n"],
    ['web/src/a.test.js', OLD_JS, "xit('b', () => { expect(1).toBe(1); });\n"],
  ];
  for (const [file, old, extra] of cases) {
    const root = makeRepo();
    commit(root, { [file]: `${old}${extra}` });
    assert.deepEqual(kinds(run(root)), [`added-skip:${file}`], extra);
  }
});

test('removing an assertion without adding one is flagged with the counts', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': 'def test_a():\n    assert 1 == 1\n', 'web/src/a.test.js': "it('a', () => {\n  expect(1).toBe(1);\n});\n" });
  const flags = run(root);
  assert.deepEqual(kinds(flags).sort(), ['net-removed-assertions:scraper/tests/test_a.py', 'net-removed-assertions:web/src/a.test.js']);
  assert.match(flags.find((f) => f.file.endsWith('.py')).detail, /2 -> 1/);
});

test('pytest.raises and unittest assert methods count as assertions', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': 'def test_a():\n    with pytest.raises(ValueError):\n        f()\n    self.assertEqual(1, 1)\n' });
  assert.deepEqual(run(root), []);
});

test('swapping an assertion for another one is not flagged', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': 'def test_a():\n    assert 1 == 1\n    assert 2 == 3 - 1\n' });
  assert.deepEqual(run(root), []);
});

test('commenting an assertion out is flagged', () => {
  const root = makeRepo();
  commit(root, { 'scraper/tests/test_a.py': 'def test_a():\n    assert 1 == 1\n    # assert 2 == 2\n', 'web/src/a.test.js': "it('a', () => {\n  expect(1).toBe(1);\n  // expect(2).toBe(2);\n});\n" });
  assert.deepEqual(kinds(run(root)).sort(), ['net-removed-assertions:scraper/tests/test_a.py', 'net-removed-assertions:web/src/a.test.js']);
});

test('non-test files and unrelated changes are ignored', () => {
  const root = makeRepo();
  commit(root, { 'scraper/a.py': 'X = 2\n', 'README.md': 'hi\n' });
  assert.deepEqual(run(root), []);
});

test('commits that landed on the base after the branch point are not blamed on the branch', () => {
  const root = makeRepo();
  sh(root, 'checkout', '-q', '-b', 'feature');
  commit(root, { 'scraper/a.py': 'X = 2\n' });
  sh(root, 'checkout', '-q', 'main');
  commit(root, { 'scraper/tests/test_a.py': null });
  sh(root, 'update-ref', 'refs/remotes/origin/main', 'HEAD');
  assert.deepEqual(run(root, { head: 'feature' }), []);
});

test('a test file replaced by a symlink is flagged', () => {
  const root = makeRepo();
  fs.rmSync(path.join(root, 'scraper/tests/test_a.py'));
  fs.symlinkSync('../a.py', path.join(root, 'scraper/tests/test_a.py'));
  sh(root, 'add', '-A');
  sh(root, 'commit', '-q', '-m', 'symlink');
  assert.deepEqual(kinds(run(root)), ['net-removed-assertions:scraper/tests/test_a.py']);
});

test('a missing repo root is reported as such, not as a bad ref', () => {
  assert.throws(() => run('/nonexistent/path/for/test'), /repo root/);
});

test('unsafe or unknown refs throw instead of reaching git as options', () => {
  const root = makeRepo();
  assert.throws(() => run(root, { base: '--output=/tmp/x' }), /unsafe base ref/);
  assert.throws(() => run(root, { head: 'a..b' }), /unsafe head ref/);
  assert.throws(() => run(root, { base: 'origin/nope' }), /does not exist/);
});
