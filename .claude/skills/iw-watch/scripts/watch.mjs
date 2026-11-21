#!/usr/bin/env node
// iw-watch runner. The runner decides what to do (poll, filter, dedupe, cap); the model decides how.
//   watch.mjs scan [--mine] [--review-requested] [--author L] [--max-rounds N] [--json]
//   watch.mjs ack <item-id>...
// Exit codes: 0 ok (also "already running"), 2 GitHub or environment error, 64 usage error.
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { makeGh, GhError } from './lib/gh.mjs';
import { scan } from './lib/scan.mjs';
import { stateDir, loadState, saveState, ack, dropClosed, acquireLock, releaseLock } from './lib/state.mjs';

const USAGE = `usage: watch.mjs scan|ack|run [--mine] [--review-requested] [--author <login>] [--domain <dir>|mine]
                 [--max-rounds N] [--json] [--dry-run] [--limit N]
       watch.mjs ack <item-id>...`;

class UsageError extends Error {}

export function parseArgs(argv) {
  const [cmd, ...rest] = argv;
  if (!['scan', 'ack', 'run'].includes(cmd)) throw new UsageError(`unknown command ${JSON.stringify(cmd ?? '')}`);
  const o = { cmd, mine: false, reviewRequested: false, author: null, domains: [], maxRounds: 3, json: false, dryRun: false, limit: 3, ids: [] };
  const value = (flag) => {
    const v = rest.shift();
    if (v === undefined || v.startsWith('--')) throw new UsageError(`${flag} needs a value`);
    return v;
  };
  const count = (flag) => {
    const n = Number(value(flag));
    if (!Number.isInteger(n) || n < 1 || n > 50) throw new UsageError(`${flag} must be a whole number from 1 to 50`);
    return n;
  };
  while (rest.length) {
    const a = rest.shift();
    if (a === '--mine') o.mine = true;
    else if (a === '--review-requested') o.reviewRequested = true;
    else if (a === '--author') o.author = value(a);
    else if (a === '--domain') o.domains.push(value(a));
    else if (a === '--max-rounds') o.maxRounds = count(a);
    else if (a === '--limit') o.limit = count(a);
    else if (a === '--json') o.json = true;
    else if (a === '--dry-run') o.dryRun = true;
    else if (cmd === 'ack' && !a.startsWith('-')) o.ids.push(a);
    else throw new UsageError(`unknown argument ${JSON.stringify(a)}`);
  }
  if (o.author && !/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(o.author)) throw new UsageError('--author must be a GitHub login');
  if (cmd === 'ack' && !o.ids.length) throw new UsageError('ack needs at least one item id');
  if (o.domains.length) throw new UsageError('--domain is not implemented yet');
  if (cmd === 'scan' && (o.dryRun || o.limit !== 3)) throw new UsageError('--dry-run and --limit apply to run only');
  if (cmd !== 'ack' && !o.mine && !o.reviewRequested && !o.author && !o.domains.length) {
    throw new UsageError('say what to watch: --mine, --review-requested, --author <login> or --domain <dir>');
  }
  return o;
}

export function defaultDeps() {
  return {
    gh: makeGh(),
    env: process.env,
    home: os.homedir(),
    stdout: (s) => process.stdout.write(s),
    stderr: (s) => process.stderr.write(s),
    now: () => Date.now(),
  };
}

function context(deps) {
  const me = deps.gh(['api', 'user']).login;
  const view = deps.gh(['repo', 'view', '--json', 'nameWithOwner,defaultBranchRef']);
  return { me, repo: view.nameWithOwner, defaultBranch: view.defaultBranchRef?.name || 'main' };
}

/** Run `fn(state)` under the lock; the state is saved only when fn returns without throwing */
function withState(deps, repo, fn) {
  const dir = stateDir({ env: deps.env, home: deps.home, repo });
  const lock = acquireLock(dir, { now: deps.now });
  if (!lock) {
    deps.stderr('iw-watch: already running (lock held), nothing to do\n');
    return { skipped: true };
  }
  try {
    const state = loadState(dir, { log: (m) => deps.stderr(`${m}\n`), now: () => new Date(deps.now()) });
    const out = fn(state, dir, lock);
    saveState(dir, state);
    return out;
  } finally {
    releaseLock(lock);
  }
}

function printItems(deps, items, json) {
  if (json) {
    deps.stdout(`${JSON.stringify({ items }, null, 2)}\n`);
    return;
  }
  if (!items.length) {
    deps.stdout('iw-watch: nothing new\n');
    return;
  }
  for (const it of items) {
    const who = it.kind === 'review' ? `by ${it.author}` : `${it.events.length} new`;
    deps.stdout(`#${it.pr} ${it.kind.padEnd(14)} ${clean(who).padEnd(16)} round ${it.rounds}/${it.maxRounds}  ${clean(it.title)}\n    ${clean(it.url)}\n    id: ${it.id}\n`);
  }
}

// Titles and logins are other people's text: no terminal escape sequences reach the terminal
export const clean = (s) => String(s ?? '').replace(/[\u0000-\u001f\u007f-\u009f]/g, '?');

export async function main(argv, deps = defaultDeps()) {
  let o;
  try {
    o = parseArgs(argv);
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    deps.stderr(`iw-watch: ${e.message}\n${USAGE}\n`);
    return 64;
  }
  try {
    const ctx = context(deps);
    if (o.cmd === 'ack') {
      withState(deps, ctx.repo, (state) => { for (const id of o.ids) ack(state, id); });
      deps.stdout(`iw-watch: acknowledged ${o.ids.join(', ')}\n`);
      return 0;
    }
    if (o.cmd === 'scan') {
      const res = withState(deps, ctx.repo, (state) => {
        const r = scan({ gh: deps.gh, repo: ctx.repo, me: ctx.me, mode: { mine: o.mine, reviewRequested: o.reviewRequested, author: o.author }, state, maxRounds: o.maxRounds, warn: (m) => deps.stderr(`${m}\n`) });
        if (r.open) dropClosed(state, r.open);
        return r;
      });
      if (!res.skipped) printItems(deps, res.items, o.json);
      return 0;
    }
    deps.stderr('iw-watch: run is not implemented yet\n');
    return 64;
  } catch (e) {
    if (e instanceof GhError) {
      deps.stderr(`iw-watch: ${e.kind}: ${e.message}\n`);
      return 2;
    }
    if (/not an item id|not pending/.test(e.message)) {
      deps.stderr(`iw-watch: ${e.message}\n`);
      return 64;
    }
    throw e;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; });
}
