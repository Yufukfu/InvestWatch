import test from 'node:test';
import assert from 'node:assert/strict';
import { main } from './watch.mjs';
import { domainFilter } from './lib/scan.mjs';
import { parseCodeowners } from './lib/codeowners.mjs';
import { buildPrompt } from './lib/prompt.mjs';
import { cli, fx, ME } from './testkit.mjs';

const CODEOWNERS = '/scraper/ @hen68\n/web/ @kacpermalczyk\n/infra/ @kacpermalczyk\n/analytics/ @Yufukfu\n/.github/ @org/maintainers\n';
const pr = (number, author, paths, over = {}) => ({ ...fx('pr-28.json'), number, url: `https://github.com/Yufukfu/InvestWatch/pull/${number}`, headRefOid: `${number}`.padStart(40, 'a'), author: { login: author }, files: paths.map((p) => ({ path: p })), ...over });
const quiet = (n) => ({ [`pulls/${n}/reviews`]: [], [`pulls/${n}/comments`]: [], [`issues/${n}/comments`]: [] });

function domainCli(prs, { codeowners = CODEOWNERS, over = {} } = {}) {
  const routes = { 'pr list all': prs, 'pr list open': prs.map((p) => ({ number: p.number })), ...Object.assign({}, ...prs.map((p) => quiet(p.number))), ...over };
  const c = cli(routes);
  const gitCalls = [];
  c.deps.mainRoot = '/repo/InvestWatch';
  c.deps.git = (args) => {
    gitCalls.push(args);
    if (args.includes('show')) {
      if (codeowners === null) throw new Error('fatal: path does not exist');
      return codeowners;
    }
    return '';
  };
  const ghCalls = [];
  const gh = c.deps.gh;
  c.deps.gh = (args) => { ghCalls.push(args); return gh(args); };
  return { ...c, gitCalls, ghCalls, items: () => JSON.parse(c.out.join('')).items };
}

test('--domain scraper: a PR that changes only web/ is not reported, one that touches scraper/ is', async () => {
  const c = domainCli([pr(40, 'Yufukfu', ['web/src/a.ts']), pr(41, 'Yufukfu', ['scraper/collectors/x.py', 'web/src/a.ts'])]);
  assert.equal(await main(['scan', '--domain', 'scraper', '--json'], c.deps), 0, c.err.join(''));
  assert.deepEqual(c.items().map((i) => [i.pr, i.kind]), [[41, 'review']]);
});

test('--domain mine: every directory I own, so a PR on infra/compose.yaml is a review for me', async () => {
  const c = domainCli([pr(42, 'hen68', ['infra/compose.yaml']), pr(43, 'hen68', ['analytics/r.py'])]);
  assert.equal(await main(['scan', '--domain', 'mine', '--json'], c.deps), 0, c.err.join(''));
  assert.deepEqual(c.items().map((i) => i.pr), [42]);
});

test('--domain with a trailing slash or a leading one names the same directory', async () => {
  for (const d of ['scraper/', '/scraper', 'scraper']) {
    const c = domainCli([pr(41, 'Yufukfu', ['scraper/a.py'])]);
    await main(['scan', '--domain', d, '--json'], c.deps);
    assert.equal(c.items().length, 1, d);
  }
});

test('an unknown domain exits non-zero naming it, before any PR is fetched', async () => {
  const c = domainCli([pr(41, 'Yufukfu', ['scraper/a.py'])]);
  assert.equal(await main(['scan', '--domain', 'frontend', '--json'], c.deps), 64);
  assert.match(c.err.join(''), /frontend/);
  assert.ok(!c.ghCalls.some((a) => a[0] === 'pr'), 'no PR was fetched');
});

test('--domain without a CODEOWNERS file on the default branch is an error', async () => {
  const c = domainCli([pr(41, 'Yufukfu', ['scraper/a.py'])], { codeowners: null });
  assert.equal(await main(['scan', '--domain', 'scraper', '--json'], c.deps), 64);
  assert.match(c.err.join(''), /CODEOWNERS/);
});

test('CODEOWNERS is read from origin/<default branch>, never from the PR', async () => {
  const c = domainCli([pr(44, 'Yufukfu', ['.github/CODEOWNERS', 'scraper/a.py'])]);
  await main(['scan', '--domain', 'scraper', '--json'], c.deps);
  const show = c.gitCalls.find((a) => a.includes('show'));
  assert.deepEqual(show.slice(-2), ['show', 'origin/main:.github/CODEOWNERS']);
  assert.ok(c.gitCalls.some((a) => a.includes('fetch') && a.includes('main')), 'the default branch is fetched first');
});

test('--author keeps only PRs by that login', async () => {
  const c = domainCli([pr(45, 'hen68', ['scraper/a.py']), pr(46, 'Yufukfu', ['analytics/r.py'])], { over: { 'pr list author hen68': [pr(45, 'hen68', ['scraper/a.py'])] } });
  await main(['scan', '--author', 'hen68', '--json'], c.deps);
  assert.deepEqual(c.items().map((i) => [i.pr, i.author]), [[45, 'hen68']]);
});

test('--author narrows --review-requested to that author', async () => {
  const both = [pr(50, 'hen68', ['scraper/a.py']), pr(51, 'Yufukfu', ['analytics/r.py'])];
  const c = domainCli(both, { over: { 'pr list review': both } });
  await main(['scan', '--review-requested', '--author', 'Yufukfu', '--json'], c.deps);
  assert.deepEqual(c.items().map((i) => i.pr), [51]);
});

test('--domain and --mine together keep only my PRs in that domain', async () => {
  const mine = [pr(47, ME, ['web/a.ts']), pr(48, ME, ['scraper/a.py'])];
  const review = { id: 1, user: { login: 'hen68', type: 'User' }, author_association: 'COLLABORATOR', state: 'COMMENTED', body: 'nit', commit_id: 'x', submitted_at: '2026-11-21T20:00:00Z', html_url: 'u' };
  const c = domainCli(mine, { over: { 'pr list mine': mine, 'pulls/47/reviews': [review], 'pulls/48/reviews': [review] } });
  await main(['scan', '--mine', '--domain', 'web', '--json'], c.deps);
  assert.deepEqual(c.items().map((i) => i.pr), [47]);
});

test('domainFilter: a file list at the gh limit is completed from the API before filtering', () => {
  const rules = parseCodeowners(CODEOWNERS);
  const f = domainFilter(rules, ['scraper'], ME);
  assert.equal(f(['web/a.ts']), false);
  assert.equal(f(['scraper/x/y.py']), true);
  assert.equal(f(['scraper-old/x.py']), false);
  assert.throws(() => domainFilter(rules, ['nope'], ME), /nope/);
  assert.throws(() => domainFilter(rules, ['mine'], 'nobody'), /owns no directory/);
});

test('a PR with 100 files gets its full file list before the domain filter runs', async () => {
  const many = Array.from({ length: 100 }, (_, i) => `web/f${i}.ts`);
  const big = pr(49, 'Yufukfu', many);
  const c = domainCli([big], { over: { 'pulls/49/files': [...many, 'scraper/late.py'].map((filename) => ({ filename })) } });
  await main(['scan', '--domain', 'scraper', '--json'], c.deps);
  assert.deepEqual(c.items().map((i) => i.pr), [49]);
  assert.ok(c.ghCalls.some((a) => a.join(' ').includes('pulls/49/files') && a.includes('--paginate')));
});

test('the session prompt routes defects to the owner, and has rules for no owner and team owners', () => {
  const item = { repo: 'Yufukfu/InvestWatch', id: '11.address-review.abc', kind: 'address-review', pr: 11, title: 't', url: 'u', author: ME, headRef: 'web/fe', headSha: 'a'.repeat(40), baseRef: 'main', files: [], rounds: 0, maxRounds: 3, events: [], checks: [] };
  const owners = [{ path: 'analytics/r.py', owners: ['Yufukfu'] }, { path: '.docs/STATUS.md', owners: [] }, { path: '.github/ci.yml', owners: ['org/maintainers'] }];
  const p = buildPrompt({ item, me: ME, owners, nonce: 'n' });
  assert.match(p, /analytics\/r\.py: @Yufukfu/);
  assert.match(p, /\.docs\/STATUS\.md: no owner/);
  assert.match(p, /no owner[^\n]*do not open an issue[^\n]*Needs @kacpermalczyk/i);
  assert.match(p, /team[^\n]*assign/i);
  assert.match(p, /--assignee <owner login>/);
});
