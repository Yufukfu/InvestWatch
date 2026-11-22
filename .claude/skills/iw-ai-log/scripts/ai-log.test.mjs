import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkLog, renderLog, newEntry } from './ai-log.mjs';

const entry = (who, what = 'did a thing', outcome = 'PR #1') =>
  `---\nwhen: Sat 14:30\nwho: ${who}\n---\n\n## What was done with AI\n\n${what}\n\n## Outcome / lesson\n\n${outcome}\n`;

function repo(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-log-'));
  fs.mkdirSync(path.join(root, '.docs/ai-log'), { recursive: true });
  for (const [name, text] of Object.entries(files)) fs.writeFileSync(path.join(root, '.docs/ai-log', name), text);
  return root;
}

test('a well-formed entry passes and README is ignored', () => {
  const root = repo({ 'README.md': '# x', '2026-11-21T1430-adam-x.md': entry('Adam') });
  assert.deepEqual(checkLog(root), []);
});

test('bad file name, unknown or mismatched who, and a missing section are reported', () => {
  const root = repo({
    'notes.md': entry('Adam'),
    '2026-11-21T1430-adam-a.md': entry('Bob'),
    '2026-11-21T1431-adam-b.md': entry('Kacper'),
    '2026-11-21T1432-adam-c.md': '---\nwhen: x\nwho: Adam\n---\n\n## What was done with AI\n\nx\n',
  });
  const problems = checkLog(root).map((p) => `${path.basename(p.file)}: ${p.problem}`);
  assert.equal(problems.length, 4, problems.join('\n'));
  assert.match(problems.join('\n'), /notes\.md: file name/);
  assert.match(problems.join('\n'), /a\.md: `who:` must be one of/);
  assert.match(problems.join('\n'), /b\.md: `who: Kacper` does not match/);
  assert.match(problems.join('\n'), /c\.md: missing or empty section "## Outcome \/ lesson"/);
});

test('a log table back in ai-workflow.md is reported', () => {
  const root = repo({});
  fs.writeFileSync(path.join(root, '.docs/ai-workflow.md'), '## Log\n\n| When | Who | What was done with AI | Outcome / lesson |\n');
  assert.match(checkLog(root)[0].problem, /log table again/);
});

test('render sorts by file name and keeps a cell on one line with pipes escaped', () => {
  const root = repo({
    '2026-11-22T0100-kacper-late.md': entry('Kacper', 'second'),
    '2026-11-21T0900-damian-early.md': entry('Damian', 'first\nline two', 'a | b'),
  });
  const rows = renderLog(root).trim().split('\n');
  assert.equal(rows.length, 4);
  assert.equal(rows[2], '| Sat 14:30 | Damian | first line two | a \\| b |');
  assert.match(rows[3], /\| Kacper \| second \|/);
});

test('new creates a template that fails check until filled in, and refuses to overwrite', () => {
  const root = repo({});
  const rel = newEntry(root, 'kacper', 'My Change!', 'Sun 10:00', new Date(2026, 10, 22, 10, 5));
  assert.equal(rel, '.docs/ai-log/2026-11-22T1005-kacper-my-change.md');
  assert.equal(checkLog(root).length, 2);
  assert.throws(() => newEntry(root, 'kacper', 'my-change', 'x', new Date(2026, 10, 22, 10, 5)), /already exists/);
  assert.throws(() => newEntry(root, 'bob', 'x'), /who must be one of/);
});

test('the committed log is valid', () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
  assert.deepEqual(checkLog(root), []);
});
