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
    '.github/CODEOWNERS': '/scraper/ @a\n/analytics/ @b\n/web/ @c\n',
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

// ---- CODEOWNERS is the only place that says who owns which path ----

const OWNERS_OK = '# comment\n/scraper/ @hen68\n/web/ @kacpermalczyk\n/api/ @Yufukfu @org/team\n/infra/ @Yufukfu\n';

test('a service directory needs a CODEOWNERS file', () => {
  const problems = checkDocs(repo({ 'scraper/CLAUDE.md': '#' }));
  assert.equal(problems.length, 1);
  assert.match(problems[0].problem, /\.github\/CODEOWNERS/);
});

test('every existing service directory and infra/ needs a CODEOWNERS line with a handle', () => {
  const root = repo({
    'scraper/CLAUDE.md': '#', 'web/CLAUDE.md': '#', 'api/CLAUDE.md': '#', 'infra/CLAUDE.md': '#',
    '.github/CODEOWNERS': OWNERS_OK,
  });
  assert.deepEqual(checkDocs(root), []);
});

test('flags a service directory missing from CODEOWNERS, a commented-out line and a line with no handle', () => {
  const root = repo({
    'scraper/CLAUDE.md': '#', 'web/CLAUDE.md': '#', 'api/CLAUDE.md': '#',
    '.github/CODEOWNERS': '# /scraper/ @hen68\n/web/ # @kacpermalczyk\n/api/ hen68\n',
  });
  const problems = checkDocs(root).map((p) => p.problem).sort();
  assert.equal(problems.length, 3, problems.join('\n'));
  for (const dir of ['api', 'scraper', 'web']) assert.ok(problems.some((p) => p.includes(`/${dir}/`)), dir);
});

test('infra/ needs a CODEOWNERS line too', () => {
  const root = repo({ 'infra/CLAUDE.md': '#', '.github/CODEOWNERS': '/scraper/ @hen68\n' });
  const problems = checkDocs(root);
  assert.equal(problems.length, 1);
  assert.match(problems[0].problem, /\/infra\//);
});

test('the last CODEOWNERS line for a directory wins, as on GitHub', () => {
  const root = repo({ 'api/CLAUDE.md': '#', '.github/CODEOWNERS': '/api/ @Yufukfu\n/api/\n' });
  assert.equal(checkDocs(root).length, 1, 'a later bare /api/ leaves api/ without an owner');
  const back = repo({ 'api/CLAUDE.md': '#', '.github/CODEOWNERS': '/api/\n/api/ @Yufukfu\n' });
  assert.deepEqual(checkDocs(back), []);
});

test('/dir, /dir/ and /dir/** name the same directory', () => {
  for (const pattern of ['/api', '/api/', '/api/**']) {
    assert.deepEqual(checkDocs(repo({ 'api/CLAUDE.md': '#', '.github/CODEOWNERS': `${pattern} @Yufukfu\n` })), [], pattern);
  }
  const mixed = repo({ 'api/CLAUDE.md': '#', '.github/CODEOWNERS': '/api/** @Yufukfu\n/api\n' });
  assert.equal(checkDocs(mixed).length, 1, 'the later /api line has no owner');
});

test('a CODEOWNERS pattern only covers its own directory', () => {
  const root = repo({ 'web/CLAUDE.md': '#', '.github/CODEOWNERS': '/web-old/ @a\nweb/ @b\n' });
  assert.equal(checkDocs(root).length, 1);
});

const OWNERSHIP = [
  '# scraper (Adam\'s module)',
  '- **Owner:** Damian',
  'Shared infrastructure, owned by Kacper.',
  'Schema from migrations (`api`, owner Damian).',
  'Modules: `infra/` (owner Kacper).',
  'ownership by directory (`scraper/` Adam, `web/` Kacper).',
  'scheduler -> scraper (Adam) -> analytics',
  '# Status: platform (Damian)',
  'Rules for the web dashboard, Kacper\'s module.',
  'Modules: web/ dashboard (Kacper).',
  'analytics/ (Damian; an api/ folder later).',
  '| Folder | Purpose | Owner |',
  'The renderer is maintained by Adam.',
  'Damian owns `analytics/` and `api/`.',
  'Kacper owns web.',
  'Owners: @hen68 (scraper)',
  '| `api/` | @Yufukfu |',
];

test('flags each per-person ownership statement in a live doc, with its line', () => {
  for (const [i, line] of OWNERSHIP.entries()) {
    const problems = checkDocs(repo({ '.docs/a.md': `ok\n${line}\n`, '.github/CODEOWNERS': '/scraper/ @hen68\n/api/ @Yufukfu\n' }));
    assert.equal(problems.length, 1, `${line} -> ${JSON.stringify(problems)}`);
    assert.equal(problems[0].line, 2, line);
    assert.match(problems[0].problem, /ownership/, `case ${i}`);
  }
});

test('history, in-flight changes, prose about work and spec scenario steps may name people', () => {
  const body = OWNERSHIP.join('\n');
  const root = repo({
    '.docs/decisions/0101-x.md': body,
    '.docs/decisions/README.md': '0101-x.md',
    '.docs/ai-workflow.md': body,
    'openspec/changes/some-change/proposal.md': body,
    'api/README.md': 'Scraper (Adam), insert a document. Kacper\'s review of PR #35. Fixed (Adam, PR #48). In mock-api (Adam, PR #48). The mock-api (Adam) fix landed. Dashboard part (Kacper) and scraper part (Adam) pending. Fixed in api (Adam, PR #48). Reviewed by @hen68 (PR #39).',
    'openspec/specs/x/spec.md': '- **GIVEN** `analytics/` is owned by Damian\n- **THEN** the result is Adam\n',
    'README.md': 'Owners: [`.github/CODEOWNERS`](.github/CODEOWNERS)',
    '.github/CODEOWNERS': '/api/ @Yufukfu\n',
    'api/CLAUDE.md': '#',
  });
  assert.deepEqual(checkDocs(root), []);
});

test('a CODEOWNERS handle is an ownership claim only next to a module name, and not as a PR credit', () => {
  const root = repo({
    '.github/CODEOWNERS': '/scraper/ @hen68\n',
    'scraper/CLAUDE.md': '#',
    '.docs/a.md': 'The scraper fix was reviewed by @hen68 (PR #39).\n@hen68 approved it.\nweb builds with @types/node.\n',
    '.docs/b.md': 'Ask @hen68 about scraper changes.\n',
  });
  assert.deepEqual(checkDocs(root).map((p) => `${p.file}:${p.line}`), ['.docs/b.md:1']);
});

test('the scenario-step exemption applies to specs only', () => {
  const root = repo({ 'CLAUDE.md': '- **AND** Owner: Damian\n', 'openspec/specs/x/spec.md': '- **AND** Owner: Damian\n' });
  assert.deepEqual(checkDocs(root).map((p) => p.file), ['CLAUDE.md']);
});

test('only ADR files are history: the decisions index is a live doc', () => {
  const root = repo({
    '.docs/decisions/0101-x.md': '- **Owner:** Damian\n',
    '.docs/decisions/README.md': '0101-x.md\n- **Owner:** Damian\n',
    '.github/CODEOWNERS': '/api/ @Yufukfu\n',
  });
  assert.deepEqual(checkDocs(root).map((p) => `${p.file}:${p.line}`), ['.docs/decisions/README.md:2']);
});

test('prose naming a person next to "owns" or "maintained" without a module is not an ownership claim', () => {
  const root = repo({
    'api/README.md': 'Adam owns the follow-up. The cache is maintained by the worker. Kacper owns up to the bug.\n',
    'api/CLAUDE.md': '#',
    '.github/CODEOWNERS': '/api/ @Yufukfu\n',
  });
  assert.deepEqual(checkDocs(root), []);
});

test('also reads openspec/config.yaml and compose.yaml headers', () => {
  const root = repo({
    'openspec/config.yaml': 'context: |\n  Modules: scraper/ (owner Adam)\n',
    'api/compose.yaml': '# api/ deployment unit (owner Damian).\n',
    'api/compose.renderer.yaml': '# Page renderer (owner Adam)\n',
    'infra/compose.dev-ports.yml': 'x: 1\n# owner Kacper\n',
    'compose.yaml': '# root compose\n',
    'api/CLAUDE.md': '#',
    'infra/CLAUDE.md': '#',
    '.github/CODEOWNERS': '/api/ @Yufukfu\n/infra/ @Yufukfu\n',
  });
  const files = checkDocs(root).map((p) => `${p.file}:${p.line}`).sort();
  assert.deepEqual(files, ['api/compose.renderer.yaml:1', 'api/compose.yaml:1', 'infra/compose.dev-ports.yml:2', 'openspec/config.yaml:2']);
});
