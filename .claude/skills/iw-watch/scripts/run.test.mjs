// `run` end to end with real git (a bare "origin", a main clone, disposable clones) and a stub `claude`
// that behaves like an agent: commits a fix, writes the reply, pushes or gets denied.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { main } from './watch.mjs';
import { fakeGh, fx, ME } from './testkit.mjs';
import { MARKER } from './lib/rounds.mjs';

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

// behaviour: 'push' | 'denied' | 'local' | 'fail'
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
    const branch = git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD');
    if (behaviour === 'push' && allowedOf(args).includes(`Bash(git push origin ${branch})`)) {
      git(cwd, 'push', '-q', 'origin', branch);
      return { status: 0, stdout: stream(), stderr: '' };
    }
    const denials = behaviour === 'denied' ? [{ tool_name: 'Bash', tool_use_id: 't', tool_input: { command: `git push origin ${branch}` } }] : [];
    return { status: 0, stdout: stream(denials), stderr: '' };
  };
}

function setup({ behaviour = 'push', over = {}, env = {}, notify } = {}) {
  const r = repo();
  const pr11 = { ...fx('pr-11.json'), headRefName: 'web/fe', headRefOid: r.feSha, baseRefName: 'main', files: [{ path: 'web/a.ts' }] };
  const pr28 = { ...fx('pr-28.json'), headRefName: 'analytics/x', headRefOid: r.axSha, baseRefName: 'main', files: [{ path: 'analytics/r.py' }] };
  const out = []; const err = []; const calls = []; const notified = [];
  const deps = {
    gh: fakeGh({ 'pr list mine': [pr11], 'pr list review': [pr28], 'pr list open': [{ number: 11 }, { number: 28 }], ...over }).gh,
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
  return { ...r, deps, out, err, calls, notified, notices, stateDir, clone, pr11, pr28 };
}

test('run --mine: the agent fixes, pushes its branch and replies; the clone is removed and the item acknowledged', async () => {
  const s = setup();
  assert.equal(await main(['run', '--mine'], s.deps), 0, s.err.join(''));
  assert.equal(s.calls.length, 1);
  assert.equal(s.calls[0].file, 'claude');
  assert.notEqual(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'origin/web/fe moved: the fix was pushed');
  assert.equal(git(s.origin, 'log', '-1', '--format=%s', 'web/fe'), 'fix(web): address review');
  assert.ok(!fs.existsSync(s.clone(11)), 'clone removed after a clean run');
  assert.equal(git(s.mainRoot, 'rev-parse', 'HEAD'), s.feSha, 'the main clone is untouched');
  const [n] = s.notices();
  assert.equal(n.kind, 'done');
  assert.equal(n.pr, 11);
  const state = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'state.json'), 'utf8'));
  assert.equal(state.prs[11].sessions, 1);
  assert.equal(state.prs[11].pending, undefined, 'acknowledged');
  const drafts = fs.readdirSync(path.join(s.stateDir, 'drafts'));
  assert.equal(drafts.length, 1);
  assert.match(fs.readFileSync(path.join(s.stateDir, 'drafts', drafts[0], 'reply.md'), 'utf8'), /iw-watch/);
  const session = JSON.parse(fs.readFileSync(path.join(s.stateDir, 'drafts', drafts[0], 'session.json'), 'utf8'));
  assert.equal(session.cost, 0.42);
  s.out.length = 0;
  assert.equal(await main(['run', '--mine'], s.deps), 0);
  assert.equal(s.calls.length, 1, 'nothing new: no second session');
});

test('run: the session runs in a disposable clone of the PR branch, with the prompt on stdin', async () => {
  const s = setup();
  await main(['run', '--mine'], s.deps);
  const c = s.calls[0];
  assert.equal(c.opts.cwd, s.clone(11));
  assert.match(c.opts.input, /untrusted-data/);
  assert.ok(!c.args.some((a) => a.includes('IGNORE') || a.includes(fx('reviews-11.json')[0].body.slice(0, 20))), 'no third-party text in argv');
  assert.ok(c.args.includes('Bash(git push origin web/fe)'));
  assert.ok(c.args.includes('Bash(gh pr comment 11 --body-file .iw-watch/reply.md)'));
});

test('run: a denied push leaves a draft, keeps the clone and tells the human', async () => {
  const s = setup({ behaviour: 'denied' });
  assert.equal(await main(['run', '--mine'], s.deps), 0);
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
  assert.ok(fs.existsSync(s.clone(11)), 'clone kept with the local commit');
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /push was denied/);
  assert.ok(n.path && fs.existsSync(path.join(n.path, 'reply.md')));
});

test('run: commits left unpushed without a denial also need the human', async () => {
  const s = setup({ behaviour: 'local' });
  await main(['run', '--mine'], s.deps);
  const [n] = s.notices();
  assert.equal(n.kind, 'needs-human');
  assert.match(n.detail, /1 commit.*not pushed/);
});

test('run --dry-run: no push or GitHub write is allowed, the result is a draft with publish commands', async () => {
  const s = setup({ behaviour: 'push' });
  await main(['run', '--mine', '--dry-run'], s.deps);
  const args = allowedOf(s.calls[0].args);
  assert.ok(args.length > 0);
  assert.ok(!args.some((a) => /git push|gh pr comment|gh issue (create|comment)/.test(a)));
  assert.equal(git(s.origin, 'rev-parse', 'web/fe'), s.feSha, 'nothing pushed');
  const [n] = s.notices();
  assert.equal(n.kind, 'draft-ready');
  assert.ok(fs.existsSync(path.join(n.path, 'reply.md')));
  assert.match(n.detail, /git push origin web\/fe/);
  assert.match(n.detail, /gh pr comment 11 --body-file/);
  assert.ok(fs.existsSync(s.clone(11)), 'the local commits stay in the clone');
});

test('run --review-requested: review in a clone of the PR head, read-only allow-list, clone removed', async () => {
  const s = setup();
  await main(['run', '--review-requested'], s.deps);
  assert.equal(s.calls.length, 1);
  const c = s.calls[0];
  assert.equal(c.opts.cwd, s.clone(28));
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
  assert.equal(s.notices()[0].kind, 'done');
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
  for (const flags of [['--dry-run'], []]) {
    const s = setup();
    s.deps.spawnClaude = () => ({ status: 0, stdout: stream([{ tool_name: 'Write', tool_input: { file_path: '.iw-watch/reply.md' } }]), stderr: '' });
    await main(['run', '--mine', ...flags], s.deps);
    const [n] = s.notices();
    assert.equal(n.kind, 'needs-human', flags.join(' ') || 'live');
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
  await main(['run', '--mine', '--dry-run'], s.deps);
  const text = s.notified[0].args[3];
  assert.match(text, /Q: Pager now or later\?/);
  assert.ok(text.includes("gh pr comment 11 --body '/iw pager: teraz'"));
  assert.ok(!/rm -rf ~'|;/.test(text.split('\n').filter((l) => l.includes('gh pr comment')).join('\n')), 'nothing to paste that runs more than the comment');
  assert.equal(s.notices()[0].questions.length, 1);
});

test('run: --limit caps the sessions per run', async () => {
  const s = setup();
  await main(['run', '--mine', '--review-requested', '--limit', '1'], s.deps);
  assert.equal(s.calls.length, 1);
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

test('notify: IWATCH_NOTIFY_CMD gets kind, title and url as argv, no shell; a failing notifier does not fail the run', async () => {
  const s = setup({ env: { IWATCH_NOTIFY_CMD: '/usr/local/bin/my-notify --flag' } });
  await main(['run', '--mine'], s.deps);
  const [c] = s.notified;
  assert.equal(c.file, '/usr/local/bin/my-notify');
  assert.deepEqual(c.args.slice(0, 1), ['--flag']);
  assert.deepEqual(c.args.slice(1, 3), ['done', `#11 ${s.pr11.title}`]);
  const u = setup({ env: { IWATCH_NOTIFY_CMD: 'n' } });
  u.deps.gh = fakeGh({ 'pr list mine': [{ ...u.pr11, title: 'bad \u001b]52;c;x\u0007 title' }], 'pr list open': [{ number: 11 }] }).gh;
  await main(['run', '--mine'], u.deps);
  assert.ok(!u.notified[0].args.join(' ').includes('\u001b'), 'no control characters reach the notifier');
  assert.equal(c.args[3], s.pr11.url);
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
