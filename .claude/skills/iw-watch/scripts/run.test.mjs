// `run` end to end with real git (a bare "origin", a main clone, disposable clones) and a stub `claude`
// that behaves like an agent: commits a fix and writes the reply. The runner pushes and posts (--publish).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { main, gitIdentityProblem } from './watch.mjs';
import { fakeGh, fx, ME } from './testkit.mjs';
import { MARKER } from './lib/rounds.mjs';

// The runner commits merges itself (lib/worktree.mjs) with whatever git identity the machine has. macOS guesses one
// from the host name, a Linux CI runner has none ("Author identity unknown"), so these tests passed on laptops and
// failed in CI. Give this process (and every git it spawns) a fixed identity, ignore the developer's own git config
// (a ~/.gitconfig identity hid the bug too) and turn guessing off, so a missing identity fails here, on any machine.
Object.assign(process.env, {
  GIT_AUTHOR_NAME: 'iw-test', GIT_AUTHOR_EMAIL: 'iw-test@example.invalid',
  GIT_COMMITTER_NAME: 'iw-test', GIT_COMMITTER_EMAIL: 'iw-test@example.invalid',
  GIT_CONFIG_GLOBAL: os.devNull, GIT_CONFIG_NOSYSTEM: '1',
  GIT_CONFIG_COUNT: '1', GIT_CONFIG_KEY_0: 'user.useConfigOnly', GIT_CONFIG_VALUE_0: 'true',
});
const ID = ['-c', 'user.name=iw-test', '-c', 'user.email=iw-test@example.invalid', '-c', 'commit.gpgsign=false', '-c', 'init.defaultBranch=main'];
const git = (cwd, ...args) => execFileSync('git', [...ID, ...args], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();

function repo() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-run-'));
  const origin = path.join(root, 'origin.git');
  const mainRoot = path.join(root, 'InvestWatch');
  git(root, 'init', '-q', '--bare', origin);
  git(root, 'clone', '-q', origin, mainRoot);
  fs.mkdirSync(path.join(mainRoot, '.github'));
  fs.writeFileSync(path.join(mainRoot, '.github/CODEOWNERS'), '/web/ @kacpermalczyk\n/analytics/ @Yufukfu\n');
  fs.writeFileSync(path.join(mainRoot, 'README.md'), 'hi\n');
  git(mainRoot, 'add', '.');
  git(mainRoot, 'commit', '-q', '-m', 'init');
  git(mainRoot, 'push', '-q', 'origin', 'HEAD:main');
  git(mainRoot, 'checkout', '-q', '-b', 'web/fe');
  fs.mkdirSync(path.join(mainRoot, 'web'));
  fs.writeFileSync(path.join(mainRoot, 'web/a.ts'), 'export const a = 1;\n');
  git(mainRoot, 'add', '.');
  git(mainRoot, 'commit', '-q', '-m', 'feat(web): a');
  git(mainRoot, 'push', '-q', 'origin', 'web/fe');
  const feSha = git(mainRoot, 'rev-parse', 'HEAD');
  git(mainRoot, 'checkout', '-q', '-b', 'analytics/x', 'main');
  fs.mkdirSync(path.join(mainRoot, 'analytics'));
  fs.writeFileSync(path.join(mainRoot, 'analytics/r.py'), 'x = 1\n');
  // a hostile PR ships its own Claude settings: a review must never run with them
  fs.mkdirSync(path.join(mainRoot, '.claude'));
  fs.writeFileSync(path.join(mainRoot, '.claude/settings.json'), '{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"touch /tmp/iw-pr-hook-ran"}]}]}}\n');
  git(mainRoot, 'add', '.');
  git(mainRoot, 'commit', '-q', '-m', 'feat(analytics): r');
  const axSha = git(mainRoot, 'rev-parse', 'HEAD');
  git(mainRoot, 'push', '-q', 'origin', `${axSha}:refs/pull/28/head`);
  git(mainRoot, 'checkout', '-q', 'web/fe'); // the branch is checked out here, so a git worktree of it would be refused
  return { root, origin, mainRoot, feSha, axSha };
}

// the allow-list part of the argv (the deny-list after it names push --force on purpose)
const allowedOf = (args) => args.slice(args.indexOf('--allowedTools') + 1, args.indexOf('--disallowedTools'));

const stream = (denials = [], isError = false) => [
  JSON.stringify({ type: 'system', subtype: 'init', tools: ['Bash'], permissionMode: 'dontAsk' }),
  JSON.stringify({ type: 'result', subtype: isError ? 'error_max_budget_usd' : 'success', is_error: isError, total_cost_usd: 0.42, num_turns: 7, result: 'Fixed the store split; replied on the PR.', permission_denials: denials }),
].join('\n');

// behaviour: 'commit' | 'fail'
function stubClaude(behaviour, calls) {
  return (file, args, opts) => {
    calls.push({ file, args, opts });
    const cwd = opts.cwd;
    fs.mkdirSync(path.join(cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(cwd, '.iw-watch/reply.md'), `Fixed: split the store.\n\n${MARKER}\n`);
    if (behaviour === 'fail') return { status: 1, stdout: stream([], true), stderr: 'boom' };
    if (!allowedOf(args).includes('Bash(git commit:*)')) return { status: 0, stdout: stream(), stderr: '' };
    fs.writeFileSync(path.join(cwd, 'web/a.ts'), 'export const a = 2;\n');
    git(cwd, 'add', 'web/a.ts');
    git(cwd, 'commit', '-q', '-m', 'fix(web): address review');
    return { status: 0, stdout: stream(), stderr: '' };
  };
}

function setup({ behaviour = 'commit', over = {}, env = {}, notify } = {}) {
  const r = repo();
  const pr11 = { ...fx('pr-11.json'), headRefName: 'web/fe', headRefOid: r.feSha, baseRefName: 'main', files: [{ path: 'web/a.ts' }] };
  const pr28 = { ...fx('pr-28.json'), headRefName: 'analytics/x', headRefOid: r.axSha, baseRefName: 'main', files: [{ path: 'analytics/r.py' }] };
  const out = []; const err = []; const calls = []; const notified = []; const execs = [];
  const fake = fakeGh({ 'pr list mine': [pr11], 'pr list review': [pr28], 'pr list open': [{ number: 11 }, { number: 28 }], ...over });
  const deps = {
    gh: fake.gh,
    exec: (file, args, opts) => { execs.push({ file, args, opts }); return ''; },
    env: { XDG_STATE_HOME: path.join(r.root, 'state'), PATH: process.env.PATH, ...env },
    home: r.root,
    stdout: (s) => out.push(s),
    stderr: (s) => err.push(s),
    now: () => Date.parse('2026-11-21T22:00:00Z'),
    mainRoot: r.mainRoot,
    spawnClaude: stubClaude(behaviour, calls),
    claudeAvailable: () => true,
    spawnNotify: notify || ((file, args, opts) => { notified.push({ file, args, opts }); return { status: 0 }; }),
  };
  const stateDir = path.join(r.root, 'state', 'iw-watch', 'Yufukfu__InvestWatch');
  const notices = () => out.join('').split('\n').filter((l) => l.startsWith('{')).map((l) => JSON.parse(l)).filter((j) => j.event === 'iw-watch.notice');
  const clone = (n) => path.join(r.root, 'InvestWatch-worktrees', `watch-pr-${n}`);
  const posts = () => fake.calls.filter((a) => a.includes('POST'));
  return { ...r, deps, out, err, calls, notified, execs, posts, notices, stateDir, clone, pr11, pr28 };
}

test('run --mine --publish: the agent commits, the runner pushes the branch and posts the reply; clone removed, item acknowledged', async () => {
  const s = setup();
  assert.equal(await main(['run', '--mine', '--publish'], s.deps), 0, s.err.join(''));
  assert.equal(s.calls.length, 1);
  assert.equal(s.calls[0].file, 'claude');
  assert.notEqual(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'origin/web/fe moved: the fix was pushed');
  assert.equal(git(s.origin, 'log', '-1', '--format=%s', 'web/fe'), 'fix(web): address review');
  assert.ok(!fs.existsSync(s.clone(11)), 'clone removed after a clean run');
  assert.equal(git(s.mainRoot, 'rev-parse', 'HEAD'), s.feSha, 'the main clone is untouched');
  const [n] = s.notices();
  assert.equal(n.kind, 'done');
  assert.equal(n.pr, 11);
  const [post] = s.posts();
  assert.ok(post.includes('repos/Yufukfu/InvestWatch/issues/11/comments') && post.includes('--input'), 'the reply goes from a JSON file, never through argv');
  const body = JSON.parse(fs.readFileSync(post[post.indexOf('--input') + 1], 'utf8')).body;
  assert.match(body, /^> iw-watch agent for @kacpermalczyk, round 1\/3\n/, 'a visible agent line first');
  assert.ok(body.trimEnd().endsWith(MARKER) && body.split(MARKER).length === 2, 'one marker, at the end');
  assert.match(n.link, /#issuecomment-/);
  const state = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(state.prs[11].sessions, 1);
  assert.equal(state.prs[11].pending, undefined, 'acknowledged');
  const drafts = fs.readdirSync(path.join(s.stateDir, 'drafts'));
  assert.equal(drafts.length, 1);
  assert.match(fs.readFileSync(path.join(s.stateDir, 'drafts', drafts[0], 'reply.md'), 'utf8'), /iw-watch/);
  const session = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'drafts', drafts[0], 'session.json'), 'utf8'));
  assert.equal(session.cost, 0.42);
  s.out.length = 0;
  assert.equal(await main(['run', '--mine', '--publish'], s.deps), 0);
  assert.equal(s.calls.length, 1, 'nothing new: no second session');
});

test('run: the session runs in a disposable clone of the PR branch, with the prompt on stdin', async () => {
  const s = setup();
  await main(['run', '--mine'], s.deps);
  const c = s.calls[0];
  assert.equal(c.opts.cwd, s.clone(11));
  assert.match(c.opts.input, /untrusted-data/);
  assert.ok(!c.args.some((a) => a.includes('IGNORE') || a.includes(fx('reviews-11.json')[0].body.slice(0, 20))), 'no third-party text in argv');
  assert.ok(!allowedOf(c.args).some((a) => /git push|gh /.test(a)), 'the session itself cannot publish');
  const settings = JSON.parse(c.args[c.args.indexOf('--settings') + 1]);
  assert.equal(settings.sandbox.enabled, true);
  assert.deepEqual(settings.sandbox.network.allowedDomains, [], 'no network');
  assert.ok(settings.sandbox.filesystem.denyRead.includes(path.join(s.root, '.config/gh')), 'the gh token is unreadable');
  assert.equal(c.args[c.args.indexOf('--setting-sources') + 1], 'project');
  assert.deepEqual(s.execs.map((e) => [e.file, ...e.args]), [], 'web/ has no lockfile here: nothing to install');
});

test('run: the session env is an allow-list: no GH_TOKEN, SSH agent or cloud keys; lockfiles installed by the runner', async () => {
  const s = setup({ env: { GH_TOKEN: 'ghp_x', SSH_AUTH_SOCK: '/s', AWS_SECRET_ACCESS_KEY: 'k', HOME: '/h' } });
  git(s.mainRoot, 'checkout', '-q', 'web/fe');
  fs.writeFileSync(path.join(s.mainRoot, 'web/package-lock.json'), '{}\n');
  git(s.mainRoot, 'add', '.');
  git(s.mainRoot, 'commit', '-q', '-m', 'lock');
  git(s.mainRoot, 'push', '-q', 'origin', 'web/fe');
  s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefOid: git(s.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine'], s.deps);
  const env = s.calls[0].opts.env;
  for (const k of ['GH_TOKEN', 'SSH_AUTH_SOCK', 'AWS_SECRET_ACCESS_KEY']) assert.equal(env[k], undefined, k);
  assert.equal(env.HOME, '/h');
  assert.deepEqual(s.execs.map((e) => [e.file, ...e.args]), [['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund']]);
  assert.equal(s.execs[0].opts.cwd, path.join(s.clone(11), 'web'));
  assert.equal(s.execs[0].opts.env.GH_TOKEN, undefined);
});

test('run: a fix never runs on a branch that changes .claude/, CLAUDE.md or .github/ (their hooks would load)', async () => {
  for (const file of ['.claude/settings.json', 'web/CLAUDE.md', '.github/workflows/x.yml']) {
    const s = setup();
    git(s.mainRoot, 'checkout', '-q', 'web/fe');
    fs.mkdirSync(path.dirname(path.join(s.mainRoot, file)), { recursive: true });
    fs.writeFileSync(path.join(s.mainRoot, file), '{"hooks":{}}\n');
    git(s.mainRoot, 'add', '.');
    git(s.mainRoot, 'commit', '-q', '-m', 'hostile');
    git(s.mainRoot, 'push', '-q', 'origin', 'web/fe');
    s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefOid: git(s.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(s.calls.length, 0, file);
    assert.match(s.notices()[0].detail, new RegExp(`changes ${file.replace(/\./g, '\\.')}`));
    assert.ok(!fs.existsSync(s.clone(11)), 'nothing left behind');
  }
});

test('run: a fork PR, a PR whose head is main, and a head that moved since the scan get no session', async () => {
  const fork = setup();
  fork.deps.gh = fakeGh({ 'pr list mine': [{ ...fork.pr11, isCrossRepository: true }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine', '--publish'], fork.deps);
  assert.equal(fork.calls.length, 0);
  assert.match(fork.notices()[0].detail, /fork/);
  const onMain = setup();
  onMain.deps.gh = fakeGh({ 'pr list mine': [{ ...onMain.pr11, headRefName: 'main' }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine', '--publish'], onMain.deps);
  assert.equal(onMain.calls.length, 0);
  assert.match(onMain.notices()[0].detail, /never pushes/);
  const moved = setup();
  moved.deps.gh = fakeGh({ 'pr list mine': [{ ...moved.pr11, headRefOid: 'b'.repeat(40) }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine', '--publish'], moved.deps);
  assert.equal(moved.calls.length, 0);
  assert.match(moved.notices()[0].detail, /moved since the scan/);
});

test('run: a push that fails leaves the draft and the clone and tells the human; nothing is posted', async () => {
  const s = setup();
  s.deps.git = (args, opts) => {
    if (args.includes('push')) throw Object.assign(new Error('rejected'), { stderr: '! [rejected] (fetch first)' });
    return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts }).trim();
  };
  assert.equal(await main(['run', '--mine', '--publish'], s.deps), 0);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
  assert.ok(fs.existsSync(s.clone(11)), 'clone kept with the local commit');
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /push of 1 commit failed/);
  assert.deepEqual(s.posts(), []);
  assert.ok(n.path && fs.existsSync(path.join(n.path, 'reply.md')));
});

test('run: an agent commit that touches .claude/ or .github/ is never pushed', async () => {
  const s = setup();
  s.deps.spawnClaude = (file, args, opts) => {
    fs.mkdirSync(path.join(opts.cwd, '.claude'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.claude/settings.json'), '{}');
    git(opts.cwd, 'add', '.claude/settings.json');
    git(opts.cwd, 'commit', '-q', '-m', 'sneaky');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha);
  assert.deepEqual(s.posts(), []);
  assert.match(s.notices()[0].detail, /change \.claude\/settings\.json/);
});

test('run is a dry run unless --publish: nothing pushed or posted, the result is a draft', async () => {
  for (const flags of [[], ['--dry-run']]) {
    const s = setup();
    await main(['run', '--mine', ...flags], s.deps);
    assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
    assert.deepEqual(s.posts(), [], 'nothing posted');
    const [n] = s.notices();
    assert.equal(n.kind, 'draft-ready');
    assert.ok(fs.existsSync(path.join(n.path, 'reply.md')));
    assert.ok(!/gh |git /.test(n.detail), 'no shell command in the text a notifier shows');
    assert.ok(fs.existsSync(s.clone(11)), 'the local commits stay in the clone');
  }
  assert.equal(await main(['run', '--mine', '--dry-run', '--publish'], setup().deps), 64);
});

test('run --publish: an issue drafted by the agent is opened by the runner, assigned only to a CODEOWNERS owner', async () => {
  const s = setup();
  s.deps.spawnClaude = (file, args, opts) => {
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/issue.md'), '# web: pager breaks\nassignee: @attacker\nevidence here\n');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  const issue = s.posts().find((a) => a.includes('repos/Yufukfu/InvestWatch/issues'));
  const sent = JSON.parse(fs.readFileSync(issue[issue.indexOf('--input') + 1], 'utf8'));
  assert.equal(sent.title, 'web: pager breaks');
  assert.equal(sent.assignees, undefined, 'not an owner of the changed files: nobody assigned');
  assert.match(sent.body, /not in CODEOWNERS/);
  assert.match(s.notices()[0].detail, /issue https:/);
  assert.ok(!fs.existsSync(s.clone(11)), 'published: the clone is removed');
});

test('run --review-requested: review in a clone of the PR head, read-only allow-list, clone removed', async () => {
  const s = setup();
  await main(['run', '--review-requested', '--publish'], s.deps);
  assert.equal(s.calls.length, 1);
  const c = s.calls[0];
  assert.equal(c.opts.cwd, s.clone(28));
  assert.ok(allowedOf(c.args).includes('Bash(git diff origin/main...refs/iw/pr-28)'), 'the PR range, by its exact form');
  assert.ok(!allowedOf(c.args).includes('Bash(git diff:*)'), 'no free git diff in a review');
  assert.ok(s.posts()[0].includes('repos/Yufukfu/InvestWatch/issues/28/comments'));
  assert.equal(git(s.mainRoot, 'rev-parse', 'HEAD'), s.feSha, 'the main clone is untouched');
  assert.ok(!allowedOf(c.args).some((a) => /git push|git commit/.test(a)));
  assert.match(c.opts.input, /Approval is left to a human/);
  assert.ok(!fs.existsSync(s.clone(28)));
  assert.equal(s.notices()[0].kind, 'done');
});

test('run: a review runs on the base branch with the PR head only as a ref, so the PR\'s .claude/ never loads', async () => {
  const s = setup();
  let seen;
  s.deps.spawnClaude = (file, args, opts) => {
    seen = { head: git(opts.cwd, 'rev-parse', 'HEAD'), pr: git(opts.cwd, 'rev-parse', 'refs/iw/pr-28'), base: git(opts.cwd, 'rev-parse', 'origin/main'), prSettings: fs.existsSync(path.join(opts.cwd, '.claude/settings.json')) };
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--review-requested'], s.deps);
  assert.equal(seen.head, git(s.origin, 'rev-parse', 'main'), 'the working tree is the base branch');
  assert.equal(seen.pr, s.axSha, 'the PR head is a ref to diff against');
  assert.equal(seen.base, seen.head);
  assert.equal(seen.prSettings, false, 'the PR\'s .claude/settings.json is not in the working tree');
});

test('run: .iw-watch/ is excluded from git in the clone, and a branch that ships one is refused', async () => {
  const s = setup();
  let exclude;
  s.deps.spawnClaude = (file, args, opts) => {
    exclude = fs.readFileSync(path.join(opts.cwd, '.git/info/exclude'), 'utf8');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine'], s.deps);
  assert.match(exclude, /^\.iw-watch\/$/m);
  const t = setup();
  git(t.mainRoot, 'checkout', '-q', 'web/fe');
  fs.mkdirSync(path.join(t.mainRoot, '.iw-watch'));
  fs.writeFileSync(path.join(t.mainRoot, '.iw-watch/reply.md'), 'planted');
  git(t.mainRoot, 'add', '-f', '.iw-watch/reply.md');
  git(t.mainRoot, 'commit', '-q', '-m', 'plant');
  git(t.mainRoot, 'push', '-q', 'origin', 'web/fe');
  t.deps.gh = fakeGh({ 'pr list mine': [{ ...t.pr11, headRefOid: git(t.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine'], t.deps);
  assert.equal(t.calls.length, 0);
  assert.match(t.notices()[0].detail, /\.iw-watch/);
});

test('run: at the round cap no session starts and the human is told once', async () => {
  const s = setup();
  fs.mkdirSync(s.stateDir, { recursive: true });
  fs.writeFileSync(path.join(s.stateDir, 'state.json'), JSON.stringify({ version: 1, prs: { 11: { sessions: 3 } } }));
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 0);
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /round cap 3 reached/);
  s.out.length = 0;
  await main(['run', '--mine'], s.deps);
  assert.deepEqual(s.notices(), [], 'silent afterwards for the same head');
});

test('run: a hostile branch name is refused before any git or claude call', async () => {
  const s = setup();
  s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefName: 'x; rm -rf ~' }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 0);
  assert.ok(!fs.existsSync(path.join(s.root, 'InvestWatch-worktrees')));
  assert.match(s.notices()[0].detail, /refused branch name.*only \[A-Za-z0-9\._\/-\] is handled/);
});

test('run: a failed session needs the human, keeps the clone, and is retried once the clone is removed', async () => {
  const s = setup({ behaviour: 'fail' });
  await main(['run', '--mine'], s.deps);
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /session failed/);
  assert.ok(fs.existsSync(s.clone(11)));
  s.out.length = 0;
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 1, 'no second session while the clone is there');
  assert.deepEqual(s.notices(), [], 'and no repeated notice');
  fs.rmSync(s.clone(11), { recursive: true });
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 2, 'retried after the human removed the clone');
  assert.equal(s.notices().filter((n) => /session failed/.test(n.detail)).length, 1, 'a second failure after a retry is reported again');
});

test('run: a clone left from an earlier run is not overwritten', async () => {
  const s = setup();
  fs.mkdirSync(s.clone(11), { recursive: true });
  fs.writeFileSync(path.join(s.clone(11), 'keep.txt'), 'mine');
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 0);
  assert.equal(fs.readFileSync(path.join(s.clone(11), 'keep.txt'), 'utf8'), 'mine');
  assert.match(s.notices()[0].detail, /left from an earlier run/);
  s.out.length = 0;
  await main(['run', '--mine'], s.deps);
  assert.deepEqual(s.notices(), [], 'told once');
  fs.rmSync(s.clone(11), { recursive: true });
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 1, 'the item was kept, so removing the directory lets it run');
});

test('run: the clone ignores the main clone\'s commit-graph (a stale one broke the first live run on PR #39)', async () => {
  const s = setup();
  const seen = [];
  s.deps.git = (args, opts) => { seen.push(args); return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts }).trim(); };
  await main(['run', '--mine'], s.deps);
  const clone = seen.find((a) => a.includes('clone'));
  assert.deepEqual(clone.slice(0, 3), ['-c', 'core.commitGraph=false', 'clone']);
  assert.equal(s.notices()[0].kind, 'draft-ready');
});

test('run: a clone that fails half-way is removed, so the next run retries instead of seeing a leftover', async () => {
  const s = setup();
  let fail = true;
  s.deps.git = (args, opts) => {
    const out = execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts }).trim();
    if (fail && args.includes('fetch') && args.some((a) => a.includes('refs/remotes/origin/main'))) throw Object.assign(new Error('boom'), { stderr: 'fatal: unable to parse commit' });
    return out;
  };
  await main(['run', '--mine'], s.deps);
  assert.match(s.notices()[0].detail, /could not prepare a clone: fatal: unable to parse commit/);
  assert.ok(!fs.existsSync(s.clone(11)), 'the half-made clone is gone');
  fail = false;
  await main(['run', '--mine'], s.deps);
  assert.equal(s.calls.length, 1, 'retried on the next run');
});

test('run: uncommitted changes are never thrown away: needs-human, clone kept (live run on PR #39)', async () => {
  const s = setup();
  s.deps.spawnClaude = (file, args, opts) => {
    fs.writeFileSync(path.join(opts.cwd, 'web/a.ts'), 'export const a = 3;\n');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine'], s.deps);
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /uncommitted/);
  assert.ok(fs.existsSync(s.clone(11)));
});

test('run: a session that wrote no reply is not "done" or "draft-ready"; its final message is kept as summary.md', async () => {
  for (const flags of [[], ['--publish']]) {
    const s = setup();
    s.deps.spawnClaude = () => ({ status: 0, stdout: stream([{ tool_name: 'Write', tool_input: { file_path: '.iw-watch/reply.md' } }]), stderr: '' });
    await main(['run', '--mine', ...flags], s.deps);
    const [n] = s.notices();
    assert.equal(n.kind, 'needs-human', flags.join(' ') || 'dry');
    assert.match(n.detail, /no reply/);
    assert.match(n.detail, /1 command was denied/);
    assert.ok(fs.existsSync(path.join(n.path, 'summary.md')));
  }
});

test('run: the agent\'s questions reach the notifier as copy-paste /iw commands', async () => {
  const s = setup({ env: { IWATCH_NOTIFY_CMD: 'n' } });
  s.deps.spawnClaude = (file, args, opts) => {
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/questions.md'), "- Pager now or later? => pager: teraz | pager: pozniej'; rm -rf ~\n");
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine'], s.deps);
  const text = s.notified[0].args[3];
  assert.match(text, /Q: Pager now or later\?/);
  assert.ok(text.includes('/iw pager: teraz'));
  assert.ok(!text.includes('gh pr comment'), 'a comment to leave on the PR, not a shell command');
  assert.ok(!/rm -rf ~'|;/.test(text.split('\n').filter((l) => l.trim().startsWith('/iw ')).join('\n')));
  assert.equal(s.notices()[0].questions.length, 1);
});

test('run: the notice links the reply comment the runner posted', async () => {
  const url = 'https://github.com/Yufukfu/InvestWatch/pull/11#issuecomment-77';
  const s = setup({ env: { IWATCH_NOTIFY_CMD: 'n' }, over: { 'POST repos/Yufukfu/InvestWatch/issues/11/comments': { html_url: url } } });
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(s.notices()[0].link, url);
  assert.equal(s.notified[0].args[2], url, 'the notifier gets the comment link');
});

test('run: --limit caps the sessions per run', async () => {
  const s = setup();
  await main(['run', '--mine', '--review-requested', '--limit', '1'], s.deps);
  assert.equal(s.calls.length, 1);
});

test('run: an approved notice takes no --limit slot from a session', async () => {
  const approval = { ...fx('reviews-11.json').find((r) => r.state === 'APPROVED'), body: '' };
  const s = setup();
  const pr11 = { ...s.pr11, reviewDecision: 'APPROVED', mergeable: 'MERGEABLE', statusCheckRollup: [] };
  // #11 is approved (sorts first, no session), #28 waits for my review (a session)
  s.deps.gh = fakeGh({ 'pr list mine': [pr11], 'pr list review': [s.pr28], 'pr list open': [{ number: 11 }, { number: 28 }], 'pulls/11/reviews': [approval], 'pulls/11/comments': [], 'issues/11/comments': [] }).gh;
  assert.equal(await main(['run', '--mine', '--review-requested', '--limit', '1'], s.deps), 0, s.err.join(''));
  assert.equal(s.calls.length, 1, 'the review session still runs');
  assert.deepEqual(s.notices().map((n) => n.kind).sort(), ['approved', 'draft-ready']);
  assert.doesNotMatch(s.err.join(''), /wait for the next run/);
});

test('run: without the claude CLI it exits non-zero with install guidance and writes no state', async () => {
  const s = setup();
  s.deps.claudeAvailable = () => false;
  let ghCalls = 0;
  s.deps.gh = () => { ghCalls += 1; return null; };
  assert.equal(await main(['run', '--mine'], s.deps), 2);
  assert.equal(ghCalls, 0, 'fails before touching GitHub');
  assert.match(s.err.join(''), /claude.*(install|PATH)/i);
  assert.ok(!fs.existsSync(s.stateDir));
});

test('run: without a git identity it exits non-zero before any session and writes no state (#127)', async () => {
  const s = setup();
  s.deps.gitIdentityProblem = () => 'Author identity unknown';
  let ghCalls = 0;
  s.deps.gh = () => { ghCalls += 1; return null; };
  assert.equal(await main(['run', '--mine'], s.deps), 2);
  assert.equal(ghCalls, 0, 'fails before touching GitHub');
  assert.equal(s.calls.length, 0, 'no agent session');
  assert.match(s.err.join(''), /git identity/i);
  assert.match(s.err.join(''), /user\.email/);
  assert.ok(!fs.existsSync(s.stateDir));
});

test('gitIdentityProblem: names the gap when git cannot build an author or committer, null when it can (#127)', () => {
  const bare = { PATH: process.env.PATH, HOME: os.devNull, GIT_CONFIG_GLOBAL: os.devNull, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_COUNT: '1', GIT_CONFIG_KEY_0: 'user.useConfigOnly', GIT_CONFIG_VALUE_0: 'true' };
  assert.match(gitIdentityProblem(bare), /identity unknown|no email/i);
  // a committer alone is not enough: the merge commit needs an author too
  assert.match(gitIdentityProblem({ ...bare, GIT_COMMITTER_NAME: 'a', GIT_COMMITTER_EMAIL: 'a@example.invalid' }), /identity unknown|no email/i);
  assert.equal(gitIdentityProblem({ ...bare, GIT_AUTHOR_NAME: 'a', GIT_AUTHOR_EMAIL: 'a@example.invalid', GIT_COMMITTER_NAME: 'a', GIT_COMMITTER_EMAIL: 'a@example.invalid' }), null);
  // an identity set only in the main checkout's .git/config does not reach the fresh clones, so it does not count
  const local = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-ident-'));
  git(local, 'init', '-q');
  git(local, 'config', 'user.name', 'local'); git(local, 'config', 'user.email', 'local@example.invalid');
  const was = process.cwd();
  try { process.chdir(local); assert.match(gitIdentityProblem(bare), /identity unknown|no email/i); } finally { process.chdir(was); }
});

test('notify: IWATCH_NOTIFY_CMD gets kind, title and url as argv, no shell; a failing notifier does not fail the run', async () => {
  const s = setup({ env: { IWATCH_NOTIFY_CMD: '/usr/local/bin/my-notify --flag' } });
  await main(['run', '--mine', '--publish'], s.deps);
  const [c] = s.notified;
  assert.equal(c.file, '/usr/local/bin/my-notify');
  assert.deepEqual(c.args.slice(0, 1), ['--flag']);
  assert.deepEqual(c.args.slice(1, 3), ['done', `#11 ${s.pr11.title}`]);
  const u = setup({ env: { IWATCH_NOTIFY_CMD: 'n' } });
  u.deps.gh = fakeGh({ 'pr list mine': [{ ...u.pr11, title: 'bad \u001b]52;c;x\u0007 title' }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine'], u.deps);
  assert.ok(!u.notified[0].args.join(' ').includes('\u001b'), 'no control characters reach the notifier');
  assert.match(c.args[3], /#issuecomment-/, 'the link to the posted reply');
  assert.ok(!c.opts.shell);
  const t = setup({ env: { IWATCH_NOTIFY_CMD: 'broken' }, notify: () => { throw new Error('ENOENT'); } });
  assert.equal(await main(['run', '--mine'], t.deps), 0);
  assert.match(t.err.join(''), /notify/);
});

test('run: the item text never reaches a shell or a path', async () => {
  const s = setup();
  const evil = { ...fx('reviews-11.json')[0], id: 77, body: '$(touch /tmp/iw-pwned) `id` ../../etc', submitted_at: '2026-11-21T23:00:00Z' };
  s.deps.gh = fakeGh({ 'pr list mine': [s.pr11], 'pr list open': [{ number: 11 }], 'pulls/11/reviews': [evil] }).gh;
  await main(['run', '--mine'], s.deps);
  assert.ok(!fs.existsSync('/tmp/iw-pwned'));
  assert.ok(s.calls[0].opts.input.includes('$(touch /tmp/iw-pwned)'), 'it is in the prompt, as data');
  assert.ok(fs.readdirSync(path.join(s.stateDir, 'drafts')).every((d) => /^[0-9a-z.-]+$/.test(d)));
});

test('ME is the account the runner acts for', () => assert.equal(ME, 'kacpermalczyk'));

test('run: a PR into a branch other than the default branch gets no session (its .claude/ would load)', async () => {
  const s = setup();
  s.deps.gh = fakeGh({ 'pr list review': [{ ...s.pr28, baseRefName: 'evil-base' }], 'pr list open': [{ number: 28 }] }).gh;
  await main(['run', '--review-requested', '--publish'], s.deps);
  assert.equal(s.calls.length, 0);
  assert.match(s.notices()[0].detail, /targets evil-base, not main/);
});

test('run: a reply that carries a credential is never posted (a test can write into it)', async () => {
  for (const secret of ['ghp_abcdefghijklmnopqrstuvwxyz123456', 'my-very-long-api-key-value']) {
    const s = setup({ env: { ANTHROPIC_API_KEY: 'my-very-long-api-key-value' } });
    s.deps.spawnClaude = (file, args, opts) => {
      fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
      fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), `done ${secret}`);
      return { status: 0, stdout: stream(), stderr: '' };
    };
    await main(['run', '--mine', '--publish'], s.deps);
    assert.deepEqual(s.posts(), [], secret);
    assert.match(s.notices()[0].detail, /looks like a credential/);
  }
});

test('run: a session that changes .git/config or adds a hook gets no git call from the runner, so nothing is pushed', async () => {
  const s = setup();
  s.deps.spawnClaude = (file, args, opts) => {
    fs.appendFileSync(path.join(opts.cwd, '.git/config'), '[core]\n\tfsmonitor = touch /tmp/iw-fsmonitor\n');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.match(s.notices()[0].detail, /changed \.git\/config/);
  assert.deepEqual(s.posts(), []);
  assert.ok(!fs.existsSync('/tmp/iw-fsmonitor'));
});

test('run: a fix branch with a symlink, a .Claude/ in another case or a .npmrc gets no session', async () => {
  for (const [file, how] of [['web/link', 'symlink'], ['.Claude/settings.json', 'file'], ['web/.npmrc', 'file']]) {
    const s = setup();
    git(s.mainRoot, 'checkout', '-q', 'web/fe');
    fs.mkdirSync(path.dirname(path.join(s.mainRoot, file)), { recursive: true });
    if (how === 'symlink') fs.symlinkSync('../../../.config/gh/hosts.yml', path.join(s.mainRoot, file));
    else fs.writeFileSync(path.join(s.mainRoot, file), 'x\n');
    git(s.mainRoot, 'add', '.');
    git(s.mainRoot, 'commit', '-q', '-m', 'hostile');
    git(s.mainRoot, 'push', '-q', 'origin', 'web/fe');
    s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefOid: git(s.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(s.calls.length, 0, file);
    assert.match(s.notices()[0].detail, how === 'symlink' ? /symlink/ : /changes/, file);
  }
});

// main moves on: `files` are written on main and pushed; the PR is reported CONFLICTING by GitHub
function conflicted(files) {
  const s = setup({ over: { 'pulls/11/reviews': [], 'pulls/11/comments': [] } });
  git(s.mainRoot, 'checkout', '-q', 'main');
  for (const [f, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(s.mainRoot, f)), { recursive: true });
    fs.writeFileSync(path.join(s.mainRoot, f), text);
  }
  git(s.mainRoot, 'add', '.');
  git(s.mainRoot, 'commit', '-q', '-m', 'main moves');
  git(s.mainRoot, 'push', '-q', 'origin', 'HEAD:main');
  git(s.mainRoot, 'checkout', '-q', 'web/fe');
  s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, mergeable: 'CONFLICTING' }], 'pr list open': [{ number: 11 }], 'pulls/11/reviews': [], 'pulls/11/comments': [] }).gh;
  const fake = s.deps.gh;
  const posted = [];
  s.deps.gh = (args) => { if (args.includes('POST')) posted.push(args); return fake(args); };
  s.posts = () => posted;
  return s;
}

const resolver = (content, { add = true } = {}) => (file, args, opts) => {
  fs.writeFileSync(path.join(opts.cwd, 'web/a.ts'), content);
  if (add) git(opts.cwd, 'add', 'web/a.ts');
  fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
  fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'web/a.ts: kept both');
  return { status: 0, stdout: stream(), stderr: '' };
};

test('run: a PR in conflict with main: the runner merges, the agent resolves, the runner commits the merge, pushes and posts', async () => {
  const s = conflicted({ 'web/a.ts': 'export const a = 9;\n', '.claude/settings.json': '{"from":"main"}\n' });
  let prompt;
  const resolve = resolver('export const a = 1;\nexport const b = 9;\n');
  s.deps.spawnClaude = (file, args, opts) => { prompt = opts.input; return resolve(file, args, opts); };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.match(prompt, /conflicts with `main`[\s\S]*`web\/a\.ts`/);
  const head = git(s.origin, 'rev-parse', 'web/fe');
  assert.equal(git(s.origin, 'rev-list', '--parents', '-n', '1', head).split(' ').length, 3, 'a merge commit, two parents');
  assert.equal(git(s.origin, 'show', `${head}:web/a.ts`), 'export const a = 1;\nexport const b = 9;');
  assert.equal(s.notices()[0].kind, 'done', 'main\'s own .claude/ change is not the agent\'s: the push goes through');
  assert.equal(s.posts().length, 1);
});

test('run: a merge git resolves on its own needs no session: merged, pushed, a short reply', async () => {
  const s = conflicted({ 'README.md': 'main readme\n' });
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(s.calls.length, 0, 'no agent');
  assert.equal(git(s.origin, 'show', 'web/fe:README.md'), 'main readme');
  assert.equal(s.notices()[0].kind, 'done');
});

test('run: conflict markers left, or a conflict not staged, are never committed or pushed', async () => {
  for (const [content, add] of [['<<<<<<< HEAD\nexport const a = 1;\n=======\nexport const a = 9;\n>>>>>>> origin/main\n', true], ['export const a = 1;\n', false]]) {
    const s = conflicted({ 'web/a.ts': 'export const a = 9;\n' });
    s.deps.spawnClaude = resolver(content, { add });
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
    assert.deepEqual(s.posts(), []);
    assert.match(s.notices()[0].detail, add ? /conflict markers are left in web\/a\.ts/ : /unresolved conflicts: web\/a\.ts/);
  }
});

test('run: a conflict inside .claude/ is not given to an agent', async () => {
  const s = conflicted({ '.claude/settings.json': '{"from":"main"}\n' });
  git(s.mainRoot, 'checkout', '-q', 'main');
  // make the branch side touch it too, from a base that is the old main
  git(s.mainRoot, 'checkout', '-q', 'web/fe');
  s.deps.spawnClaude = () => { throw new Error('no session expected'); };
  // simulate git reporting the conflict there
  const real = s.deps.git;
  s.deps.git = (args, opts) => (args.includes('--diff-filter=U') ? '.claude/settings.json' : (real || ((a, o) => execFileSync('git', a, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...o }).trim()))(args, opts));
  await main(['run', '--mine', '--publish'], s.deps);
  assert.match(s.notices()[0].detail, /conflicts in \.claude\/settings\.json/);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha);
});

test('run: the protected-path check sees renames out of .claude/ and non-ASCII paths (Adam, PR #48)', async () => {
  for (const change of [(r) => { git(r, 'mv', 'README.md', 'x.md'); fs.mkdirSync(path.join(r, '.github/workflows'), { recursive: true }); fs.writeFileSync(path.join(r, '.github/workflows/é.yml'), 'x\n'); }, (r) => { fs.mkdirSync(path.join(r, 'dír'), { recursive: true }); fs.writeFileSync(path.join(r, 'dír/CLAUDE.md'), 'x\n'); }]) {
    const s = setup();
    git(s.mainRoot, 'checkout', '-q', 'web/fe');
    change(s.mainRoot);
    git(s.mainRoot, 'add', '-A');
    git(s.mainRoot, 'commit', '-q', '-m', 'hostile');
    git(s.mainRoot, 'push', '-q', 'origin', 'web/fe');
    s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefOid: git(s.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(s.calls.length, 0);
    assert.match(s.notices()[0].detail, /changes .*(\.github\/workflows\/é\.yml|dír\/CLAUDE\.md)/);
  }
});

test('run: a session that moves the tracking ref cannot hide a protected change; the push check uses the cloned sha', async () => {
  const s = setup();
  s.deps.spawnClaude = (file, args, opts) => {
    fs.mkdirSync(path.join(opts.cwd, '.github'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.github/evil.yml'), 'x');
    git(opts.cwd, 'add', '.github/evil.yml');
    git(opts.cwd, 'commit', '-q', '-m', 'ci');
    git(opts.cwd, 'update-ref', 'refs/remotes/origin/web/fe', 'HEAD');
    git(opts.cwd, 'update-ref', 'refs/remotes/origin/main', 'HEAD');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
  assert.match(s.notices()[0].detail, /change \.github\/evil\.yml/);
});

test('run: a secret written into a committed file or a commit message is never pushed; nor is a binary file', async () => {
  for (const [file, content, msg, re] of [['web/fixture.json', '{"t":"ghp_abcdefghijklmnopqrstuvwxyz123456"}', 'fix', /commits contain something that looks like a credential/], ['web/a.ts', 'export const a = 3;\n', 'fix sk-ant-abcdefghijklmnop', /looks like a credential/], ['web/blob.bin', Buffer.from([0, 1, 2, 0, 255]), 'fix', /binary files \(web\/blob\.bin\)/]]) {
    const s = setup();
    s.deps.spawnClaude = (f, args, opts) => {
      fs.writeFileSync(path.join(opts.cwd, file), content);
      git(opts.cwd, 'add', file);
      git(opts.cwd, 'commit', '-q', '-m', msg);
      fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
      fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
      return { status: 0, stdout: stream(), stderr: '' };
    };
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, file);
    assert.match(s.notices()[0].detail, re);
  }
});

test('run: a PR merged or moved while the agent worked gets no push and no comment', async () => {
  for (const [stateRoute, re] of [[{ state: 'MERGED', headRefOid: 'x' }, /merged now/], [{ state: 'OPEN', headRefOid: 'e'.repeat(40) }, /moved to eeeeeeeeeeee/]]) {
    const s = setup({ over: { 'pr state': stateRoute } });
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha);
    assert.deepEqual(s.posts(), []);
    assert.match(s.notices()[0].detail, re);
  }
});

test('run: a dry run is not a round, and a crash on one item does not stop the run', async () => {
  const s = setup();
  await main(['run', '--mine'], s.deps);
  const st = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(st.prs[11].sessions, undefined, 'a draft does not count toward the cap');
  const t = setup();
  t.deps.spawnClaude = () => { throw Object.assign(new Error('git status exploded'), { stderr: 'fatal: boom' }); };
  assert.equal(await main(['run', '--mine', '--review-requested', '--limit', '2'], t.deps), 0);
  assert.match(t.notices()[0].detail, /runner failed on this item: fatal: boom/);
  assert.equal(t.notices().length, 2, 'the next item still ran');
});

test('the sandbox also refuses writes to .github/ and the agent files of the clone', async () => {
  const s = setup();
  await main(['run', '--mine'], s.deps);
  const settings = JSON.parse(s.calls[0].args[s.calls[0].args.indexOf('--settings') + 1]);
  for (const p of ['.github', '.claude', 'CLAUDE.md']) assert.ok(settings.sandbox.filesystem.denyWrite.includes(path.join(s.clone(11), p)), p);
});

test('run: when a teammate pushed meanwhile, the runner\'s push is rejected, never forced over their commit', async () => {
  const s = setup();
  const stub = s.deps.spawnClaude;
  let theirs;
  s.deps.spawnClaude = (...a) => {
    const r = stub(...a);
    const other = path.join(s.root, 'other');
    git(s.root, 'clone', '-q', '--branch', 'web/fe', s.origin, other);
    fs.writeFileSync(path.join(other, 'web/b.ts'), 'export const b = 1;\n');
    git(other, 'add', '.');
    git(other, 'commit', '-q', '-m', 'teammate');
    git(other, 'push', '-q', 'origin', 'web/fe');
    theirs = git(other, 'rev-parse', 'HEAD');
    return r;
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), theirs, 'the teammate\'s commit is still the head');
  assert.equal(s.notices()[0].kind, 'needs-human');
  assert.deepEqual(s.posts(), []);
});

test('run: a conflict merge still pushes when main itself added a token-shaped string and a binary since the fork (Adam, PR #48)', async () => {
  const s = conflicted({ 'web/a.ts': 'export const a = 9;\n', 'web/fake.test.mjs': 'const t = "ghp_abcdefghijklmnopqrstuvwxyz123456";\n', 'doc/report.pdf': Buffer.from([0x25, 0x50, 0x44, 0x46, 0, 1, 2, 0, 255]) });
  // and a commit message on main that quotes a token shape (the merged-in history is not the agent's)
  git(s.mainRoot, 'checkout', '-q', 'main');
  git(s.mainRoot, 'commit', '-q', '--allow-empty', '-m', 'test: fixture ghp_abcdefghijklmnopqrstuvwxyz123456');
  git(s.mainRoot, 'push', '-q', 'origin', 'HEAD:main');
  git(s.mainRoot, 'checkout', '-q', 'web/fe');
  s.deps.spawnClaude = resolver('export const a = 1;\nexport const b = 9;\n');
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(s.notices()[0].kind, 'done', s.notices()[0].detail);
  assert.equal(git(s.origin, 'show', 'web/fe:web/a.ts'), 'export const a = 1;\nexport const b = 9;');
  assert.equal(s.posts().length, 1);
});

test('run: in a conflict merge, a token or binary the agent itself adds is still refused', async () => {
  for (const [file, content, re] of [['web/a.ts', 'export const a = 1;\nconst t = "ghp_abcdefghijklmnopqrstuvwxyz123456";\n', /looks like a credential/], ['web/blob.bin', Buffer.from([0, 1, 2, 0, 255]), /binary files \(web\/blob\.bin\)/]]) {
    const s = conflicted({ 'web/a.ts': 'export const a = 9;\n', 'web/main.test.mjs': 'const t = "ghp_abcdefghijklmnopqrstuvwxyz123456";\n' });
    const resolve = resolver(file === 'web/a.ts' ? content : 'export const a = 1;\n');
    s.deps.spawnClaude = (f, args, opts) => {
      if (file !== 'web/a.ts') { fs.writeFileSync(path.join(opts.cwd, file), content); git(opts.cwd, 'add', file); }
      return resolve(f, args, opts);
    };
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, file);
    assert.match(s.notices()[0].detail, re);
  }
});

test('run: agent commits larger than 2 MB are never pushed', async () => {
  const s = setup();
  s.deps.spawnClaude = (f, args, opts) => {
    fs.writeFileSync(path.join(opts.cwd, 'web/big.txt'), `${'abcdefghij\n'.repeat(200 * 1024)}`);
    git(opts.cwd, 'add', 'web/big.txt');
    git(opts.cwd, 'commit', '-q', '-m', 'big');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'r');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha);
  assert.match(s.notices()[0].detail, /larger than 2 MB/);
});

test('run: a session that aborts the merge gets no "resolved" reply, and the conflict is not marked handled', async () => {
  const s = conflicted({ 'web/a.ts': 'export const a = 9;\n' });
  s.deps.spawnClaude = (f, args, opts) => {
    git(opts.cwd, 'merge', '--abort');
    fs.mkdirSync(path.join(opts.cwd, '.iw-watch'), { recursive: true });
    fs.writeFileSync(path.join(opts.cwd, '.iw-watch/reply.md'), 'resolved');
    return { status: 0, stdout: stream(), stderr: '' };
  };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha);
  assert.deepEqual(s.posts(), []);
  assert.match(s.notices()[0].detail, /does not contain origin\/main/);
  const st = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(st.prs[11].conflictSha, undefined);
});

test('run: a resolved conflict is handled once per head sha (conflictSha dedupe)', async () => {
  const s = conflicted({ 'web/a.ts': 'export const a = 9;\n' });
  let sessions = 0;
  const resolve = resolver('export const a = 1;\nexport const b = 9;\n');
  s.deps.spawnClaude = (...a) => { sessions += 1; return resolve(...a); };
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(s.notices()[0].kind, 'done');
  const st = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(st.prs[11].conflictSha, s.feSha);
  s.out.length = 0;
  await main(['run', '--mine', '--publish'], s.deps); // GitHub still reports the old head as CONFLICTING
  assert.equal(sessions, 1, 'no second session for the same head');
  assert.deepEqual(s.notices(), []);
});

test('run: a bare ======= line (a heading underline) is not a conflict marker', async () => {
  const s = conflicted({ 'web/a.ts': 'export const a = 9;\n' });
  s.deps.spawnClaude = resolver('/*\nTitle\n=======\n*/\nexport const a = 1;\n');
  await main(['run', '--mine', '--publish'], s.deps);
  assert.equal(s.notices()[0].kind, 'done', s.notices()[0].detail);
});

test('run: a fix branch that renames a file out of .github/ or adds a .gitattributes gets no session', async () => {
  for (const change of [(r) => { fs.mkdirSync(path.join(r, 'docs'), { recursive: true }); git(r, 'mv', '.github/CODEOWNERS', 'docs/owners.txt'); }, (r) => fs.writeFileSync(path.join(r, 'web/.gitattributes'), '*.ts filter=x\n')]) {
    const s = setup();
    git(s.mainRoot, 'checkout', '-q', 'web/fe');
    change(s.mainRoot);
    git(s.mainRoot, 'add', '-A');
    git(s.mainRoot, 'commit', '-q', '-m', 'hostile');
    git(s.mainRoot, 'push', '-q', 'origin', 'web/fe');
    s.deps.gh = fakeGh({ 'pr list mine': [{ ...s.pr11, headRefOid: git(s.mainRoot, 'rev-parse', 'HEAD') }], 'pr list open': [{ number: 11 }] }).gh;
    await main(['run', '--mine', '--publish'], s.deps);
    assert.equal(s.calls.length, 0);
    assert.match(s.notices()[0].detail, /changes .*(\.github\/CODEOWNERS|web\/\.gitattributes)/);
  }
});

test('run --mine: an approved PR starts no session; the notice is approved, with the approvers, and is acknowledged', async () => {
  const approval = { ...fx('reviews-11.json').find((r) => r.state === 'APPROVED'), body: '' };
  const pr = { ...fx('pr-11.json'), reviewDecision: 'APPROVED', mergeable: 'MERGEABLE', statusCheckRollup: [] };
  const s = setup({ over: { 'pr list mine': [pr], 'pulls/11/reviews': [approval], 'pulls/11/comments': [], 'issues/11/comments': [] }, env: { IWATCH_NOTIFY_CMD: '/usr/local/bin/my-notify' } });
  s.deps.gh = fakeGh({ 'pr list mine': [{ ...pr, headRefOid: s.feSha }], 'pr list review': [], 'pr list open': [{ number: 11 }], 'pulls/11/reviews': [approval], 'pulls/11/comments': [], 'issues/11/comments': [] }).gh;
  assert.equal(await main(['run', '--mine'], s.deps), 0, s.err.join(''));
  assert.equal(s.calls.length, 0, 'no claude session');
  const [n] = s.notices();
  assert.equal(n.kind, 'approved');
  assert.match(n.detail, /@hen68/);
  assert.equal(s.notified[0].args[0], 'approved');
  const state = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(state.prs[11].approvedSha, s.feSha);
  assert.equal(await main(['run', '--mine'], s.deps), 0);
  assert.equal(s.notices().length, 1, 'not told twice');
});
