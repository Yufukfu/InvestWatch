import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { scan } from './lib/scan.mjs';
import { makeGh, GhError } from './lib/gh.mjs';
import { main } from './watch.mjs';
import { ack } from './lib/state.mjs';
import { MARKER } from './lib/rounds.mjs';

const fx = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'));
const REPO = 'Yufukfu/InvestWatch';
const ME = 'kacpermalczyk';

// A fake `gh` answering from saved fixtures. `over` replaces any route; every call is recorded.
function fakeGh(over = {}) {
  const pr11 = fx('pr-11.json');
  const pr28 = fx('pr-28.json');
  const routes = {
    'api user': { login: ME },
    'repo view': { nameWithOwner: REPO, defaultBranchRef: { name: 'main' } },
    'pr list mine': [pr11],
    'pr list review': [pr28],
    'pr list open': [{ number: 11 }, { number: 28 }],
    'pulls/11/reviews': fx('reviews-11.json'),
    'pulls/11/comments': fx('review-comments-11.json'),
    'issues/11/comments': [],
    'pulls/28/reviews': [],
    'pulls/28/comments': [],
    'issues/28/comments': [],
    ...over,
  };
  const calls = [];
  const gh = (args) => {
    calls.push(args);
    const s = args.join(' ');
    let key;
    if (s === 'api user') key = 'api user';
    else if (s.startsWith('repo view')) key = 'repo view';
    else if (s.startsWith('pr list') && args.includes('--author') && args[args.indexOf('--author') + 1] === '@me') key = 'pr list mine';
    else if (s.startsWith('pr list') && s.includes('review-requested:@me')) key = 'pr list review';
    else if (s.startsWith('pr list') && args.includes('--author')) key = `pr list author ${args[args.indexOf('--author') + 1]}`;
    else if (s.startsWith('pr list')) key = 'pr list open';
    else key = (/(pulls|issues)\/\d+\/(reviews|comments)/.exec(s) || [])[0];
    const v = routes[key];
    if (v instanceof Error) throw v;
    if (v === undefined) throw new Error(`fake gh: no route for ${s}`);
    return structuredClone(v);
  };
  return { gh, calls };
}

const empty = () => ({ version: 1, prs: {} });

test('--mine: a new review on my PR becomes one address-review item with every comment and the head sha', () => {
  const { gh } = fakeGh();
  const { items } = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: empty() });
  assert.equal(items.length, 1);
  const [it] = items;
  assert.equal(it.kind, 'address-review');
  assert.equal(it.pr, 11);
  assert.equal(it.headSha, fx('pr-11.json').headRefOid);
  const inline = it.events.filter((e) => e.type === 'review-comment');
  assert.equal(inline.length, fx('review-comments-11.json').length);
  assert.ok(it.events.some((e) => e.type === 'review' && e.state === 'CHANGES_REQUESTED'));
  assert.ok(it.events.every((e) => e.author !== ME), 'my own comments are not work for me');
  const latest = it.events.map((e) => e.at).sort().at(-1);
  assert.equal(it.id, `11.address-review.${latest}`);
});

test('--mine: nothing new after ack, exit 0 and no item', () => {
  const { gh } = fakeGh();
  const state = empty();
  const first = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state }).items[0];
  ack(state, first.id);
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state }).items, []);
});

test('--mine: a comment newer than the ack makes a new item with only that comment', () => {
  const state = empty();
  const { gh } = fakeGh();
  ack(state, scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state }).items[0].id);
  const later = { id: 1, user: { login: 'hen68', type: 'User' }, body: 'one more thing', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const g2 = fakeGh({ 'issues/11/comments': [later] }).gh;
  const items = scan({ gh: g2, repo: REPO, me: ME, mode: { mine: true }, state }).items;
  assert.equal(items.length, 1);
  assert.deepEqual(items[0].events.map((e) => e.body), ['one more thing']);
});

test('my own comments, including my agent\'s marked replies, are not work for me', () => {
  const mine = { id: 4, user: { login: ME, type: 'User' }, body: `fixed in abc\n${MARKER}`, created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const { gh } = fakeGh({ 'pulls/11/reviews': [], 'pulls/11/comments': [], 'issues/11/comments': [mine] });
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: empty() }).items, []);
});

test('bot comments and an empty approval are not work', () => {
  const bot = { id: 2, user: { login: 'github-actions[bot]', type: 'Bot' }, body: 'deploy preview', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const approve = { id: 3, user: { login: 'hen68', type: 'User' }, state: 'APPROVED', body: '', commit_id: 'x', submitted_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const { gh } = fakeGh({ 'pulls/11/reviews': [approve], 'pulls/11/comments': [], 'issues/11/comments': [bot] });
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: empty() }).items, []);
});

test('closed PRs are dropped from the state', () => {
  const state = { version: 1, prs: { 3: { seenAt: '2026-11-20T00:00:00Z' }, 11: {} } };
  const { gh } = fakeGh();
  const { open } = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state });
  assert.ok(open.has(11) && !open.has(3));
});

test('--mine: a failed check on the head sha is a ci-failed item, once per sha', () => {
  const pr = { ...fx('pr-11.json'), statusCheckRollup: fx('checks-failed.json') };
  const { gh } = fakeGh({ 'pr list mine': [pr], 'pulls/11/reviews': [], 'pulls/11/comments': [] });
  const state = empty();
  const items = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state }).items;
  assert.equal(items.length, 1);
  assert.equal(items[0].kind, 'ci-failed');
  assert.deepEqual(items[0].checks.map((c) => c.name), ['python (analytics)']);
  ack(state, items[0].id);
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state }).items, []);
});

test('--review-requested: a ready PR waiting for me is a review item with its changed paths', () => {
  const { gh } = fakeGh();
  const items = scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state: empty() }).items;
  assert.equal(items.length, 1);
  const pr28 = fx('pr-28.json');
  assert.equal(items[0].kind, 'review');
  assert.equal(items[0].id, `28.review.${pr28.headRefOid}`);
  assert.deepEqual(items[0].files, pr28.files.map((f) => f.path));
  assert.equal(items[0].author, 'Yufukfu');
});

test('--review-requested: reviewed sha is skipped, a new head sha comes back', () => {
  const state = empty();
  const { gh } = fakeGh();
  ack(state, scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state }).items[0].id);
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state }).items, []);
  const pushed = { ...fx('pr-28.json'), headRefOid: 'b'.repeat(40) };
  const items = scan({ gh: fakeGh({ 'pr list review': [pushed] }).gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state }).items;
  assert.equal(items.length, 1);
  assert.equal(items[0].headSha, 'b'.repeat(40));
});

test('--review-requested: a human review of mine on the head sha counts as reviewed', () => {
  const pr28 = fx('pr-28.json');
  const mine = { id: 9, user: { login: ME, type: 'User' }, state: 'COMMENTED', body: 'lgtm', commit_id: pr28.headRefOid, submitted_at: '2026-11-21T20:00:00Z', html_url: 'u' };
  const { gh } = fakeGh({ 'pulls/28/reviews': [mine] });
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state: empty() }).items, []);
});

test('--review-requested: a draft PR is skipped', () => {
  const { gh } = fakeGh({ 'pr list review': [{ ...fx('pr-28.json'), isDraft: true }] });
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state: empty() }).items, []);
});

test('round cap: at the cap one cap-reached item replaces the work, then silence for that sha', () => {
  const marked = [1, 2, 3].map((i) => ({ id: 100 + i, user: { login: ME, type: 'User' }, body: `round ${i}\n${MARKER}`, created_at: `2026-11-21T1${i}:00:00Z`, html_url: 'u' }));
  const { gh } = fakeGh({ 'issues/11/comments': marked });
  const state = empty();
  const items = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state, maxRounds: 3 }).items;
  assert.equal(items.length, 1);
  assert.equal(items[0].kind, 'cap-reached');
  assert.equal(items[0].rounds, 3);
  ack(state, items[0].id);
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state, maxRounds: 3 }).items, []);
  assert.equal(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state, maxRounds: 4 }).items[0].kind, 'address-review');
});

test('round cap counts recorded sessions when the agent forgot the marker', () => {
  const { gh } = fakeGh();
  const state = { version: 1, prs: { 11: { sessions: 3 } } };
  assert.equal(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state, maxRounds: 3 }).items[0].kind, 'cap-reached');
});

test('gh errors are classified: missing binary, not logged in, rate limit', () => {
  const err = (props) => () => { throw Object.assign(new Error('x'), props); };
  assert.throws(() => makeGh({ exec: err({ code: 'ENOENT' }) })(['api', 'user']), (e) => e instanceof GhError && e.kind === 'missing' && /install/.test(e.message));
  assert.throws(() => makeGh({ exec: err({ status: 4, stderr: 'To get started with GitHub CLI, please run:  gh auth login' }) })(['api', 'user']), (e) => e.kind === 'auth' && /gh auth login/.test(e.message));
  assert.throws(() => makeGh({ exec: err({ status: 1, stderr: 'gh: API rate limit exceeded for user ID 1. (HTTP 403)' }) })(['api', 'user']), (e) => e.kind === 'rate');
  assert.throws(() => makeGh({ exec: err({ status: 1, stderr: 'HTTP 404: Not Found' }) })(['api', 'x']), (e) => e.kind === 'other');
});

test('gh is called with an argv array and never a shell', () => {
  const seen = [];
  const gh = makeGh({ exec: (file, args, opts) => { seen.push({ file, args, opts }); return '{"ok":true}'; } });
  assert.deepEqual(gh(['api', 'user']), { ok: true });
  assert.equal(seen[0].file, 'gh');
  assert.ok(Array.isArray(seen[0].args));
  assert.ok(!seen[0].opts.shell);
});

// --- the CLI, with the same fake gh ---

function cli(over = {}, envOver = {}) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-watch-home-'));
  const out = []; const err = [];
  const deps = {
    gh: fakeGh(over).gh,
    env: { XDG_STATE_HOME: path.join(home, 'state'), ...envOver },
    home,
    stdout: (s) => out.push(s),
    stderr: (s) => err.push(s),
    now: () => Date.parse('2026-11-21T22:00:00Z'),
  };
  return { deps, out, err, stateFile: path.join(home, 'state', 'iw-watch', 'Yufukfu__InvestWatch', 'state.json') };
}

test('CLI: scan --json prints items, does not acknowledge; ack does', async () => {
  const c = cli();
  assert.equal(await main(['scan', '--mine', '--json'], c.deps), 0);
  const { items } = JSON.parse(c.out.join(''));
  assert.equal(items.length, 1);
  c.out.length = 0;
  assert.equal(await main(['scan', '--mine', '--json'], c.deps), 0);
  assert.equal(JSON.parse(c.out.join('')).items.length, 1, 'scan alone does not acknowledge');
  assert.equal(await main(['ack', items[0].id], c.deps), 0);
  c.out.length = 0;
  await main(['scan', '--mine', '--json'], c.deps);
  assert.equal(JSON.parse(c.out.join('')).items.length, 0);
});

test('CLI: gh not logged in or rate limited exits non-zero and leaves the state file unchanged', async () => {
  for (const kind of ['auth', 'rate']) {
    const c = cli();
    await main(['scan', '--mine', '--json'], c.deps);
    const before = fs.readFileSync(c.stateFile, 'utf8');
    const inode = fs.statSync(c.stateFile).ino;
    const failing = cli({ 'pulls/11/reviews': new GhError(kind, `gh failed: ${kind}`) });
    failing.deps.env = c.deps.env;
    failing.deps.home = c.deps.home;
    const code = await main(['scan', '--mine', '--json'], failing.deps);
    assert.notEqual(code, 0, kind);
    assert.match(failing.err.join(''), new RegExp(kind));
    assert.equal(fs.readFileSync(c.stateFile, 'utf8'), before, `${kind}: state unchanged`);
    assert.equal(fs.statSync(c.stateFile).ino, inode, `${kind}: the state file is not even rewritten`);
  }
});

test('CLI: a second runner exits 0 with "already running"', async () => {
  const c = cli();
  const dir = path.dirname(c.stateFile);
  fs.mkdirSync(path.join(dir, 'lock'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'lock', 'owner.json'), JSON.stringify({ pid: 1, at: c.deps.now() }));
  assert.equal(await main(['scan', '--mine'], c.deps), 0);
  assert.match(c.err.join(''), /already running/);
});

test('CLI: no source flag, an unknown flag or a bad --max-rounds is a usage error', async () => {
  for (const argv of [['scan'], ['scan', '--mine', '--bogus'], ['scan', '--mine', '--max-rounds', '0'], ['frobnicate']]) {
    const c = cli();
    assert.equal(await main(argv, c.deps), 64, argv.join(' '));
  }
});

test('CLI: human output names the PR, the kind and the round', async () => {
  const c = cli();
  await main(['scan', '--mine'], c.deps);
  const text = c.out.join('');
  assert.match(text, /#11/);
  assert.match(text, /address-review/);
  assert.match(text, /round 0\/3/);
});
