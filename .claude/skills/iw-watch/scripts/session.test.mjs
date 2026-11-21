import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { claudeArgs, allowList, DENY, TOOLS, parseStream, runSession, childEnv, pushDenied } from './lib/session.mjs';

const help = fs.readFileSync(new URL('./fixtures/claude-help.txt', import.meta.url), 'utf8');
const stream = fs.readFileSync(new URL('./fixtures/claude-stream-denied.jsonl', import.meta.url), 'utf8');
const mine = { kind: 'address-review', pr: 11, headRef: 'web/frontend-architecture' };
const valueAfter = (args, flag) => {
  const i = args.indexOf(flag);
  const out = [];
  for (let j = i + 1; j < args.length && !args[j].startsWith('--'); j += 1) out.push(args[j]);
  return out;
};

test('every flag the runner passes exists in claude --help (Claude Code 2.1.330)', () => {
  for (const kind of ['address-review', 'ci-failed', 'review']) {
    for (const dryRun of [false, true]) {
      for (const a of claudeArgs({ ...mine, kind, dryRun, budgetUsd: 2, model: 'haiku' }).filter((x) => x.startsWith('-'))) {
        assert.ok(new RegExp(`(^|[\\s,])${a.replace(/[-]/g, '\\-')}([\\s,]|$)`, 'm').test(help), `${a} is not in claude --help`);
      }
    }
  }
  assert.ok(!/--max-turns/.test(help), 'this version has no --max-turns; the budget and a timeout bound the session');
});

test('headless mode: dontAsk, nobody to prompt, no persistence, restricted tools, budget', () => {
  const args = claudeArgs({ ...mine, dryRun: false, budgetUsd: 2 });
  assert.equal(args[0], '-p');
  assert.deepEqual(valueAfter(args, '--permission-mode'), ['dontAsk']);
  assert.deepEqual(valueAfter(args, '--permission-prompts'), ['none']);
  assert.ok(args.includes('--no-session-persistence'));
  assert.deepEqual(valueAfter(args, '--tools'), TOOLS);
  assert.deepEqual(TOOLS, ['Bash', 'Read', 'Edit', 'Write', 'Grep', 'Glob']);
  assert.deepEqual(valueAfter(args, '--max-budget-usd'), ['2']);
  assert.deepEqual(valueAfter(args, '--output-format'), ['stream-json']);
  for (const bad of ['bypassPermissions', '--dangerously-skip-permissions', '--allow-dangerously-skip-permissions', '--restricted', '--bare', '--safe-mode', '--setting-sources']) {
    assert.ok(!args.includes(bad), `${bad} would drop a guard (--bare and --restricted skip the project hook)`);
  }
});

test('the allow-list for my PR: exact branch push, this PR only, no review, merge, ready, api or network', () => {
  const allow = allowList({ ...mine, dryRun: false });
  assert.ok(allow.includes('Bash(git push origin web/frontend-architecture)'));
  assert.ok(allow.includes('Bash(gh pr comment 11:*)'));
  assert.ok(allow.includes('Bash(gh issue create:*)'));
  assert.ok(allow.includes('Bash(git commit:*)'));
  assert.ok(!allow.some((r) => /git push origin:\*|git push:\*/.test(r)), 'no wildcard push');
  for (const r of allow) {
    assert.ok(!/gh pr (review|merge|ready)|gh api|WebFetch|WebSearch|curl|wget/.test(r), r);
    assert.notEqual(r, 'Bash');
    assert.ok(!/^Bash\(\*?\)$|^Bash\(:\*\)$/.test(r), r);
  }
});

test('review of someone else\'s PR: no commit, no push, no test runners', () => {
  const allow = allowList({ kind: 'review', pr: 28, headRef: 'api/x', dryRun: false });
  assert.ok(!allow.some((r) => /git push|git commit|git add|npm|pytest|node --test/.test(r)), allow.join(' '));
  assert.ok(allow.includes('Bash(gh pr comment 28:*)'));
});

test('dry run: no push and no GitHub write at all', () => {
  for (const kind of ['address-review', 'ci-failed', 'review']) {
    const allow = allowList({ ...mine, kind, dryRun: true });
    assert.ok(!allow.some((r) => /git push|gh pr comment|gh issue (create|comment)|gh pr create/.test(r)), `${kind}: ${allow.join(' ')}`);
  }
});

test('the deny-list is passed too and names the dangerous commands', () => {
  const args = claudeArgs({ ...mine, dryRun: false, budgetUsd: 2 });
  const deny = valueAfter(args, '--disallowedTools');
  assert.deepEqual(deny, DENY);
  for (const d of ['Bash(gh pr review:*)', 'Bash(gh pr merge:*)', 'Bash(gh pr ready:*)', 'Bash(gh api:*)', 'Bash(curl:*)', 'Bash(wget:*)', 'WebFetch', 'WebSearch']) assert.ok(DENY.includes(d), d);
});

test('a branch name that is not safe never reaches the allow-list', () => {
  assert.throws(() => allowList({ ...mine, headRef: 'x) Bash(curl:*' }), /branch/);
});

test('parseStream reads a real dontAsk denial and pushDenied spots a denied push', () => {
  const r = parseStream(stream);
  assert.equal(r.isError, false);
  assert.equal(r.denials[0].tool_input.command, 'git push --force origin main');
  assert.ok(r.cost > 0);
  assert.equal(pushDenied(r.denials), true);
  assert.equal(pushDenied([{ tool_name: 'Bash', tool_input: { command: 'git status' } }]), false);
  assert.equal(pushDenied([{ tool_name: 'Bash', tool_input: { command: 'cd x && git  push origin y' } }]), true);
  assert.deepEqual(parseStream('not json\n').denials, [], 'garbage lines are skipped');
  assert.equal(parseStream('').isError, true, 'no result line means the session did not finish');
});

test('the prompt goes through stdin, never argv, and the child env has no IW_* flags', () => {
  const seen = {};
  const spawn = (file, args, opts) => { Object.assign(seen, { file, args, opts }); return { status: 0, stdout: stream, stderr: '' }; };
  const prompt = 'SECRET-PROMPT-TEXT from a review';
  const res = runSession({ spawn, cwd: '/tmp/x', prompt, args: claudeArgs({ ...mine, dryRun: false, budgetUsd: 2 }), env: { PATH: '/bin', IW_SKIP_SPEC: '1', IW_ALLOW_GIT: '1', HOME: '/h' } });
  assert.equal(seen.file, 'claude');
  assert.equal(seen.opts.input, prompt);
  assert.ok(!seen.args.some((a) => a.includes('SECRET')));
  assert.ok(!seen.opts.shell);
  assert.equal(seen.opts.cwd, '/tmp/x');
  assert.ok(seen.opts.timeout > 0);
  assert.deepEqual(Object.keys(seen.opts.env).filter((k) => k.startsWith('IW_')), []);
  assert.equal(seen.opts.env.IWATCH_SESSION, '1');
  assert.equal(res.denials.length, 1);
  assert.deepEqual(Object.keys(childEnv({ IW_X: '1', iw_y: '2', A: 'b' })).sort(), ['A', 'IWATCH_SESSION']);
});

test('a session that times out or exits non-zero is reported as failed', () => {
  const t = runSession({ spawn: () => ({ status: null, signal: 'SIGTERM', error: Object.assign(new Error('t'), { code: 'ETIMEDOUT' }), stdout: '' }), cwd: '/', prompt: 'x', args: [], env: {} });
  assert.equal(t.timedOut, true);
  assert.equal(t.ok, false);
  const f = runSession({ spawn: () => ({ status: 1, stdout: stream }), cwd: '/', prompt: 'x', args: [], env: {} });
  assert.equal(f.ok, false);
  const g = runSession({ spawn: () => ({ status: 0, stdout: stream }), cwd: '/', prompt: 'x', args: [], env: {} });
  assert.equal(g.ok, true);
});
