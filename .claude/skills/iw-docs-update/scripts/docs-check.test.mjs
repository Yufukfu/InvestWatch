import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkDocs } from './docs-check.mjs';

function repo(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-check-'));
  for (const [rel, body] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    fs.writeFileSync(path.join(root, rel), body);
  }
  return root;
}

test('a clean docs tree has no problems', () => {
  const root = repo({
    'CLAUDE.md': 'See [plan](.docs/integration-plan.md) and `.docs/STATUS.md`.',
    '.docs/integration-plan.md': '# plan',
    '.docs/STATUS.md': '# status',
  });
  assert.deepEqual(checkDocs(root), []);
});

test('flags a broken markdown link and reports file and line', () => {
  const root = repo({ '.docs/a.md': 'ok\n[gone](missing.md)\n' });
  const [p] = checkDocs(root);
  assert.equal(p.file, '.docs/a.md');
  assert.equal(p.line, 2);
  assert.match(p.problem, /missing\.md/);
});

test('flags a backticked .md path that no longer exists (renamed plan)', () => {
  const root = repo({ 'CLAUDE.md': 'Read `.docs/plan-integracji.md`.', '.docs/integration-plan.md': '#' });
  const problems = checkDocs(root);
  assert.equal(problems.length, 1);
  assert.match(problems[0].problem, /plan-integracji\.md/);
});

test('resolves paths relative to the file and to the repo root, strips anchors', () => {
  const root = repo({
    '.docs/INDEX.md': '`STATUS.md` `../.claude/SDLC.md` [x](STATUS.md#milestones) `.docs/STATUS.md`',
    '.docs/STATUS.md': '#',
    '.claude/SDLC.md': '#',
  });
  assert.deepEqual(checkDocs(root), []);
});

test('ignores URLs, globs, placeholders and per-change file names', () => {
  const root = repo({
    '.docs/a.md': '[w](https://example.com/x.md) `contracts/*.md` `<service>/CLAUDE.md` `tasks.md` `follow-ups.md` `NNNN-short-title.md`',
  });
  assert.deepEqual(checkDocs(root), []);
});

test('ADR files must be listed in the decisions index; the template is exempt', () => {
  const root = repo({
    '.docs/decisions/README.md': '| [0001](0001-tls-client.md) | TLS client |',
    '.docs/decisions/0000-template.md': '#',
    '.docs/decisions/0001-tls-client.md': '#',
    '.docs/decisions/0002-queue.md': '#',
  });
  const problems = checkDocs(root);
  assert.equal(problems.length, 1);
  assert.match(problems[0].problem, /0002-queue\.md.*not listed/);
});

test('every existing service directory needs its own CLAUDE.md', () => {
  const root = repo({
    'scraper/CLAUDE.md': '#',
    'analytics/main.py': 'x = 1',
    'web/CLAUDE.md': '#',
  });
  const problems = checkDocs(root);
  assert.equal(problems.length, 1);
  assert.equal(problems[0].file, 'analytics');
  assert.match(problems[0].problem, /CLAUDE\.md/);
});

test('service directories that do not exist yet are not required', () => {
  assert.deepEqual(checkDocs(repo({ 'CLAUDE.md': '#' })), []);
});

test('skips generated OpenSpec skills and node_modules', () => {
  const root = repo({
    '.agents/skills/x/SKILL.md': '[bad](nope.md)',
    'node_modules/p/README.md': '[bad](nope.md)',
  });
  assert.deepEqual(checkDocs(root), []);
});
