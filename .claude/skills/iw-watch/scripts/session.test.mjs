import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { claudeArgs, allowList, denyList, DENY, TOOLS, parseStream, runSession, childEnv, pushDenied } from './lib/session.mjs';

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
  assert.ok(allow.includes('Bash(gh pr comment 11 --body-file .iw-watch/reply.md)'), 'posting only this PR and only the reply file');
  assert.ok(!allow.some((r) => /gh pr comment 11 \*|gh issue comment/.test(r)), 'no free-form body file, no comment on another issue or PR');
  assert.ok(allow.includes('Read(./**)') && allow.includes('Edit(./**)'), 'file tools scoped to the clone');
  assert.ok(!allow.some((r) => ['Read', 'Write', 'Edit'].includes(r)), 'no unscoped file tool');
  assert.ok(allow.includes('Bash(gh issue create --title * --assignee * --body-file .iw-watch/issue.md)'));
  assert.ok(!allow.includes('Bash(gh issue create:*)'));
  assert.ok(!allow.includes('Bash(ls:*)'), 'ls reaches outside the clone; Glob does not');
  assert.ok(allow.includes('Bash(git commit:*)'));
  assert.ok(!allow.some((r) => /git push origin:\*|git push:\*/.test(r)), 'no wildcard push');
  assert.ok(allow.includes('Bash(npm ci --ignore-scripts:*)'), 'a fresh clone can install the lockfile, without install scripts');
  assert.ok(!allow.some((r) => /npm (install|i|ci)(:\*|\)| \*)/.test(r) || r === 'Bash(npm ci:*)' || /npm exec|npx:\*/.test(r)), 'no other install path');
  for (const r of allow) {
    assert.ok(!/gh pr (review|merge|ready)|gh api|WebFetch|WebSearch|curl|wget/.test(r), r);
    assert.notEqual(r, 'Bash');
    assert.ok(!/^Bash\(\*?\)$|^Bash\(:\*\)$/.test(r), r);
  }
});

test('review of someone else\'s PR: no commit, no push, no test runners', () => {
  const allow = allowList({ kind: 'review', pr: 28, headRef: 'api/x', dryRun: false });
  assert.ok(!allow.some((r) => /git push|git commit|git add|npm|pytest|node --test/.test(r)), allow.join(' '));
  assert.ok(allow.includes('Bash(gh pr comment 28 --body-file .iw-watch/reply.md)'));
  assert.ok(allow.includes('Edit(./.iw-watch/**)'), 'a review writes only its reply');
  assert.ok(!allow.includes('Edit(./**)'));
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
  assert.deepEqual(deny, denyList({ ...mine, dryRun: false }));
  for (const d of DENY) assert.ok(deny.includes(d), d);
  assert.ok(valueAfter(claudeArgs({ ...mine, dryRun: true, budgetUsd: 2 }), '--disallowedTools').includes('Bash(git push:*)'), 'the dry-run denies reach the argv');
  assert.ok(valueAfter(claudeArgs({ kind: 'review', pr: 28, headRef: 'api/x', dryRun: false, budgetUsd: 2 }), '--disallowedTools').includes('Bash(git commit:*)'), 'the review denies reach the argv');
  for (const d of ['Bash(gh pr review:*)', 'Bash(gh pr merge:*)', 'Bash(gh pr ready:*)', 'Bash(gh api:*)', 'Bash(curl:*)', 'Bash(wget:*)', 'WebFetch', 'WebSearch']) assert.ok(DENY.includes(d), d);
});

test('the deny-list blocks other repositories, git and settings files, and outward writes in a dry run', () => {
  const deny = denyList({ ...mine, dryRun: false });
  for (const d of ['Bash(gh * --repo *)', 'Bash(gh * --repo=*)', 'Bash(gh * -R *)', 'Bash(gh pr create:*)', 'Edit(./.git/**)', 'Edit(./.claude/**)', 'Read(./.env)']) assert.ok(deny.includes(d), d);
  const dry = denyList({ ...mine, dryRun: true });
  for (const d of ['Bash(git push:*)', 'Bash(gh pr comment:*)', 'Bash(gh issue create:*)', 'Bash(gh issue comment:*)']) assert.ok(dry.includes(d), `dry run: ${d}`);
  assert.ok(!deny.includes('Bash(git push:*)'), 'outside a dry run the exact-branch push stays possible');
  const review = denyList({ kind: 'review', pr: 28, headRef: 'api/x', dryRun: false });
  for (const d of ['Bash(git push:*)', 'Bash(git commit:*)']) assert.ok(review.includes(d), `review: ${d}`);
});

test('lessons from the live run on PR #39: cd into the clone, the reply folder, npm --prefix, oxlint', () => {
  const cwd = '/Users/x/Projects/InvestWatch-worktrees/watch-pr-39';
  const allow = allowList({ ...mine, dryRun: true, cwd });
  assert.ok(allow.includes(`Bash(cd ${cwd})`) && allow.includes(`Bash(cd ${cwd}/*)`), 'agents write "cd <clone> && git status"; every part of a chain must be allowed');
  assert.ok(!allow.some((r) => r === 'Bash(cd:*)' || r === 'Bash(cd *)'), 'cd only into the clone');
  assert.ok(allow.includes('Edit(./.iw-watch/**)'), 'Edit(./**) does not cover dot-directories (probe), so the reply folder is listed');
  for (const r of ['Bash(npm --prefix * ci --ignore-scripts)', 'Bash(npm --prefix * test:*)', 'Bash(npm --prefix * run test:*)', 'Bash(npm --prefix * run lint:*)', 'Bash(npm --prefix * run typecheck:*)', 'Bash(npx oxlint:*)']) assert.ok(allow.includes(r), r);
  const review = allowList({ kind: 'review', pr: 28, headRef: 'api/x', dryRun: false, cwd });
  assert.ok(!review.some((r) => /npm|npx/.test(r)), 'a review still runs no code');
  assert.ok(valueAfter(claudeArgs({ ...mine, dryRun: false, budgetUsd: 2, cwd }), '--allowedTools').includes(`Bash(cd ${cwd})`));
  assert.throws(() => allowList({ ...mine, cwd: '/x y/z' }), /clone path/);
});

test('read-only git and gh forms that reach outside the clone are denied (whole-branch review)', () => {
  for (const kind of ['address-review', 'review']) {
    const deny = denyList({ kind, dryRun: false });
    for (const d of ['Bash(git * --output*)', 'Bash(git * --no-index*)', 'Bash(git blame * --contents*)', 'Bash(gh * --body-file /*)', 'Bash(gh * --body-file ~*)', 'Bash(gh * --body-file ..*)', 'Bash(gh * -F *)', 'Bash(gh * --body *)', 'Bash(gh * -b *)']) assert.ok(deny.includes(d), `${kind}: ${d}`);
  }
});

test('the session environment carries no iw-watch secrets (webhook, notify command)', () => {
  const env = childEnv({ IWATCH_DISCORD_WEBHOOK: 'https://discord.com/api/webhooks/1/x', IWATCH_NOTIFY_CMD: 'n', PATH: '/bin' });
  assert.deepEqual(Object.keys(env).sort(), ['IWATCH_SESSION', 'PATH']);
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
