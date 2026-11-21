// What the runner hands to `claude -p`. Whether Claude Code enforces a rule is shown by the live probes
// (fixtures/README.md), not here; these tests pin what the runner passes and how it treats the result.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { claudeArgs, allowList, denyList, TOOLS, parseStream, runSession, childEnv, denyReadPaths, sandboxSettings } from './lib/session.mjs';

const help = fs.readFileSync(new URL('./fixtures/claude-help.txt', import.meta.url), 'utf8');
const stream = fs.readFileSync(new URL('./fixtures/claude-stream-denied.jsonl', import.meta.url), 'utf8');
const mine = { kind: 'address-review', pr: 11, baseRef: 'main' };
const valueAfter = (args, flag) => {
  const i = args.indexOf(flag);
  const out = [];
  for (let j = i + 1; j < args.length && !args[j].startsWith('--'); j += 1) out.push(args[j]);
  return out;
};

test('every flag the runner passes exists in claude --help (Claude Code 2.1.330)', () => {
  for (const kind of ['address-review', 'ci-failed', 'review']) {
    for (const a of claudeArgs({ ...mine, kind, budgetUsd: 2, model: 'haiku' }).filter((x) => x.startsWith('--'))) {
      assert.ok(new RegExp(`(^|[\\s,])${a.replace(/[-]/g, '\\-')}([\\s,]|$)`, 'm').test(help), `${a} is not in claude --help`);
    }
  }
});

test('headless and isolated: dontAsk, no prompts, project settings only, no MCP, sandbox from the CLI flag', () => {
  const args = claudeArgs({ ...mine, budgetUsd: 2 });
  assert.equal(args[0], '-p');
  assert.deepEqual(valueAfter(args, '--permission-mode'), ['dontAsk']);
  assert.deepEqual(valueAfter(args, '--permission-prompts'), ['none']);
  assert.deepEqual(valueAfter(args, '--setting-sources'), ['project'], 'no user-level allow rules, plugins or hooks');
  assert.ok(args.includes('--strict-mcp-config'), 'no MCP servers');
  assert.deepEqual(valueAfter(args, '--tools'), TOOLS);
  const s = JSON.parse(valueAfter(args, '--settings')[0]).sandbox;
  assert.equal(s.enabled, true);
  assert.equal(s.failIfUnavailable, true, 'no sandbox, no session');
  assert.equal(s.allowUnsandboxedCommands, false);
  assert.deepEqual(s.network.allowedDomains, []);
  for (const bad of ['bypassPermissions', '--dangerously-skip-permissions', '--restricted', '--bare', '--safe-mode']) assert.ok(!args.includes(bad), bad);
});

test('no session can publish: no gh, no push, in any kind', () => {
  for (const kind of ['address-review', 'ci-failed', 'review']) {
    const allow = allowList({ ...mine, kind });
    assert.ok(!allow.some((r) => /\bgh\b|git push|curl|wget|WebFetch|WebSearch/.test(r)), `${kind}: ${allow.join(' ')}`);
    assert.ok(!allow.some((r) => ['Bash', 'Read', 'Edit', 'Write'].includes(r) || /^Bash\(\*?\)$|^Bash\(:\*\)$/.test(r)), 'nothing unscoped');
    const deny = denyList({ kind });
    for (const d of ['Bash(gh:*)', 'Bash(git push:*)', 'Bash(git remote:*)', 'Bash(git config:*)', 'Edit(./.claude/**)', 'Edit(./.github/**)', 'Read(./.git/**)']) assert.ok(deny.includes(d), `${kind}: ${d}`);
  }
});

test('a review reads only the PR range by exact forms; no free git diff, no commit, no test runner', () => {
  const allow = allowList({ kind: 'review', pr: 28, baseRef: 'main' });
  assert.ok(allow.includes('Bash(git diff origin/main...refs/iw/pr-28)'));
  assert.ok(allow.includes('Bash(git show refs/iw/pr-28:*)'));
  assert.ok(!allow.some((r) => r === 'Bash(git diff:*)' || r === 'Bash(git show:*)' || /npm|pytest|node --test|git commit|git add/.test(r)), allow.join(' '));
  assert.ok(!allow.includes('Edit(./**)') && allow.includes('Edit(./.iw-watch/**)'), 'a review writes only its reply');
  assert.throws(() => allowList({ kind: 'review', pr: 28, baseRef: 'x) Bash(curl:*' }), /branch/);
});

test('git arguments that point outside the clone are denied for every reading command (Adam: git diff /abs /dev/null)', () => {
  const deny = denyList({ kind: 'address-review' });
  for (const c of ['diff', 'show', 'log', 'blame']) {
    for (const p of ['/*', '~*', '..*']) assert.ok(deny.includes(`Bash(git ${c} ${p})`) && deny.includes(`Bash(git ${c} * ${p})`), `${c} ${p}`);
  }
  assert.ok(!deny.some((d) => /npm --prefix|git commit/.test(d)), 'a fix still runs its tests and commits');
});

test('the sandbox cannot read the gh token, ssh keys, shell profiles (webhook URL), the state dir or .env files', () => {
  const paths = denyReadPaths({ home: '/h', stateDir: '/h/.local/state/iw-watch/x', configDir: '/c', envFiles: ['/p/InvestWatch/.env'] });
  for (const p of ['/h/.ssh', '/h/.config/gh', '/h/.zshenv', '/h/.aws', '/h/.netrc', '/h/.local/state/iw-watch/x', '/c', '/p/InvestWatch/.env']) assert.ok(paths.includes(p), p);
  assert.deepEqual(sandboxSettings({ denyRead: paths }).sandbox.filesystem.denyRead, paths);
});

test('the session env is an allow-list: Claude login and locale, never tokens, SSH agent, cloud keys or IW_* flags', () => {
  const env = childEnv({ PATH: '/bin', HOME: '/h', LANG: 'pl_PL.UTF-8', LC_ALL: 'C', CLAUDE_CONFIG_DIR: '/c', ANTHROPIC_API_KEY: 'k', GH_TOKEN: 'g', GITHUB_TOKEN: 'g', SSH_AUTH_SOCK: '/s', AWS_SECRET_ACCESS_KEY: 'a', IW_SKIP_SPEC: '1', IWATCH_DISCORD_WEBHOOK: 'w', NODE_OPTIONS: '--require /x' });
  assert.deepEqual(Object.keys(env).sort(), ['ANTHROPIC_API_KEY', 'CLAUDE_CONFIG_DIR', 'HOME', 'IWATCH_SESSION', 'LANG', 'LC_ALL', 'PATH']);
});

test('parseStream reads a real dontAsk denial', () => {
  const r = parseStream(stream);
  assert.equal(r.isError, false);
  assert.equal(r.denials[0].tool_input.command, 'git push --force origin main');
  assert.ok(r.cost > 0);
  assert.deepEqual(parseStream('not json\n').denials, [], 'garbage lines are skipped');
  assert.equal(parseStream('').isError, true, 'no result line means the session did not finish');
});

test('the prompt goes through stdin, never argv; claude leads its own process group', () => {
  const seen = {};
  const spawn = (file, args, opts) => { Object.assign(seen, { file, args, opts }); return { status: 0, stdout: stream, stderr: '' }; };
  const prompt = 'SECRET-PROMPT-TEXT from a review';
  const res = runSession({ spawn, cwd: '/tmp/x', prompt, args: claudeArgs({ ...mine, budgetUsd: 2 }), env: { PATH: '/bin', IW_SKIP_SPEC: '1', GH_TOKEN: 'g' } });
  assert.equal(seen.file, 'claude');
  assert.equal(seen.opts.input, prompt);
  assert.ok(!seen.args.some((a) => a.includes('SECRET')));
  assert.ok(!seen.opts.shell);
  assert.equal(seen.opts.detached, true);
  assert.equal(seen.opts.env.GH_TOKEN, undefined);
  assert.equal(res.ok, true);
});

test('a timeout or an output overflow fails the session and kills the whole process group', () => {
  for (const r of [{ status: null, signal: 'SIGKILL', error: Object.assign(new Error('t'), { code: 'ETIMEDOUT' }), stdout: '', pid: 4242 }, { status: null, error: Object.assign(new Error('b'), { code: 'ENOBUFS' }), stdout: stream, pid: 4242 }]) {
    const killed = [];
    const res = runSession({ spawn: () => r, cwd: '/', prompt: 'x', args: [], env: {}, kill: (pid) => killed.push(pid) });
    assert.equal(res.ok, false);
    assert.deepEqual(killed, [4242]);
  }
  assert.equal(runSession({ spawn: () => ({ status: 1, stdout: stream }), cwd: '/', prompt: 'x', args: [], env: {} }).ok, false);
});
