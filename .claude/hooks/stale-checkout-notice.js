#!/usr/bin/env node
/**
 * SessionStart hook: tell the agent when this checkout lags origin/main.
 *
 * Three agents push to a moving main, and a long-lived clone drifts (the main clone was 10 commits
 * behind on 2026-11-21). Anything an agent reads there is stale. This hook fetches origin/main
 * (bounded; on failure it falls back to cached refs) and injects one line of context.
 * Informational only: `git fetch` updates remote refs and nothing else, and the hook never merges,
 * resets, stashes or checks out, so uncommitted work is untouched.
 */

'use strict';

const { spawnSync } = require('child_process');

const FETCH_TIMEOUT_MS = 20000;
const GIT_TIMEOUT_MS = 5000;

function git(cwd, args, timeout = GIT_TIMEOUT_MS) {
  const res = spawnSync('git', args, { cwd, encoding: 'utf8', timeout });
  return { ok: res.status === 0, out: (res.stdout || '').trim() };
}

// The branch name is deliberately left out: `gh pr checkout` creates a local branch named by the PR author,
// so it is attacker-controlled text that would otherwise land in the agent's context.
function buildMessage({ behind, fetched }) {
  if (!behind) return null;
  const freshness = fetched ? 'just fetched' : 'fetch failed or timed out, using cached refs; may be worse';
  return (
    `Stale checkout: this checkout is ${behind} commit(s) behind origin/main (${freshness}). ` +
    'For code questions read origin/main (`git show origin/main:<path>`) or a fresh worktree ' +
    '(iw-implement), not this working tree.'
  );
}

function run(rawInput, gitFn = git) {
  let input = {};
  try {
    input = JSON.parse(rawInput || '{}');
  } catch {
    return null;
  }
  const cwd = input.cwd || process.cwd();

  if (!gitFn(cwd, ['rev-parse', '--abbrev-ref', 'HEAD']).ok) return null;

  const fetched = gitFn(cwd, ['fetch', '--quiet', 'origin', 'main'], FETCH_TIMEOUT_MS).ok;
  const behindRes = gitFn(cwd, ['rev-list', '--count', 'HEAD..origin/main']);
  if (!behindRes.ok) return null;

  const message = buildMessage({
    behind: Number.parseInt(behindRes.out, 10) || 0,
    fetched,
  });
  if (!message) return null;
  return { hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: message } };
}

if (require.main === module) {
  let stdinData = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => { stdinData += chunk; });
  process.stdin.on('end', () => {
    const output = run(stdinData);
    if (output) process.stdout.write(JSON.stringify(output));
    process.exit(0);
  });
}

module.exports = { run, buildMessage };
