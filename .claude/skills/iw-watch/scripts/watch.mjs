#!/usr/bin/env node
// iw-watch runner. The runner decides what to do (poll, filter, dedupe, cap); the model decides how.
//   watch.mjs scan [--mine] [--review-requested] [--author L] [--max-rounds N] [--json]
//   watch.mjs ack <item-id>...
//   watch.mjs run  [same filters] [--dry-run] [--limit N] [--budget-usd X] [--model M]
// Exit codes: 0 ok (also "already running"), 2 GitHub or environment error, 64 usage error.
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { makeGh, GhError } from './lib/gh.mjs';
import { scan, domainFilter, DomainError } from './lib/scan.mjs';
import { stateDir, loadState, saveState, ack, dropClosed, acquireLock, releaseLock, refreshLock, recordSession } from './lib/state.mjs';
import { loadCodeowners, ownerOf } from './lib/codeowners.mjs';
import { buildPrompt, safeBranch } from './lib/prompt.mjs';
import { claudeArgs, runSession, pushDenied } from './lib/session.mjs';
import { prepareClone, unpushed, removeClone, collectDrafts, findMainRoot, realGit, NeedsHuman } from './lib/worktree.mjs';
import { makeNotifier } from './lib/notify.mjs';
import { parseQuestions, questionsText } from './lib/questions.mjs';

const USAGE = `usage: watch.mjs scan|run [--mine] [--review-requested] [--author <login>] [--domain <dir>|mine]
                 [--max-rounds N] [--json]                                  (scan)
                 [--dry-run] [--limit N] [--budget-usd X] [--model M]       (run)
       watch.mjs ack <item-id>...`;

class UsageError extends Error {}

export function parseArgs(argv) {
  const [cmd, ...rest] = argv;
  if (!['scan', 'ack', 'run'].includes(cmd)) throw new UsageError(`unknown command ${JSON.stringify(cmd ?? '')}`);
  const o = { cmd, mine: false, reviewRequested: false, author: null, domains: [], maxRounds: 3, json: false, dryRun: false, limit: null, budgetUsd: 2, model: null, ids: [] };
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
    else if (a === '--budget-usd') {
      o.budgetUsd = Number(value(a));
      if (!(o.budgetUsd > 0 && o.budgetUsd <= 20)) throw new UsageError('--budget-usd must be more than 0 and at most 20');
    } else if (a === '--model') {
      o.model = value(a);
      if (!/^[A-Za-z0-9._-]+$/.test(o.model)) throw new UsageError('--model must be a model name or alias');
    } else if (cmd === 'ack' && !a.startsWith('-')) o.ids.push(a);
    else throw new UsageError(`unknown argument ${JSON.stringify(a)}`);
  }
  if (o.author && !/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(o.author)) throw new UsageError('--author must be a GitHub login');
  if (cmd === 'ack' && !o.ids.length) throw new UsageError('ack needs at least one item id');
  if (cmd === 'scan' && (o.dryRun || o.limit !== null || o.model)) throw new UsageError('--dry-run, --limit and --model apply to run only');
  if (cmd !== 'ack' && !o.mine && !o.reviewRequested && !o.author && !o.domains.length) {
    throw new UsageError('say what to watch: --mine, --review-requested, --author <login> or --domain <dir>');
  }
  o.limit ??= 3;
  return o;
}

export function defaultDeps() {
  return {
    gh: makeGh(),
    git: realGit,
    env: process.env,
    home: os.homedir(),
    stdout: (s) => process.stdout.write(s),
    stderr: (s) => process.stderr.write(s),
    now: () => Date.now(),
    mainRoot: null, // found from the current directory when needed
    spawnClaude: spawnSync,
    spawnNotify: spawnSync,
    claudeAvailable: () => !spawnSync('claude', ['--version'], { stdio: 'ignore' }).error,
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

function scanState(deps, ctx, o, state) {
  const mode = { mine: o.mine, reviewRequested: o.reviewRequested, author: o.author, domainFilter: ctx.domainFilter };
  const r = scan({ gh: deps.gh, repo: ctx.repo, me: ctx.me, mode, state, maxRounds: o.maxRounds, warn: (m) => deps.stderr(`${m}\n`) });
  if (r.open) dropClosed(state, r.open);
  return r;
}

/** CODEOWNERS of origin/<default branch> in the main clone (fetched first), so a PR cannot reroute itself */
function codeowners(deps, ctx) {
  const mainRoot = deps.mainRoot || findMainRoot({ git: deps.git });
  const git = (args) => deps.git(['-C', mainRoot, ...args]);
  try { git(['fetch', '--quiet', 'origin', ctx.defaultBranch]); } catch { /* offline: use what we have */ }
  return loadCodeowners({ git, ref: `origin/${ctx.defaultBranch}` });
}

function owners(deps, ctx, files) {
  let rules = null;
  try { rules = codeowners(deps, ctx); } catch (e) { deps.stderr(`iw-watch: CODEOWNERS ignored: ${e.message}\n`); }
  return files.slice(0, 200).map((p) => ({ path: p, owners: rules ? ownerOf(rules, p) : [] }));
}

function withDomains(deps, ctx, o) {
  if (!o.domains.length) return ctx;
  const rules = codeowners(deps, ctx);
  if (!rules) throw new DomainError(`--domain needs .github/CODEOWNERS on origin/${ctx.defaultBranch}`);
  return { ...ctx, domainFilter: domainFilter(rules, o.domains, ctx.me) };
}

/** One item, one headless session. Returns the notice to emit. The item is acknowledged in every case but a crash. */
function handle({ deps, ctx, o, state, sdir, mainRoot, it }) {
  const base = { pr: it.pr, title: it.title, url: it.url, item: it.id, kindOfItem: it.kind };
  if (it.kind === 'cap-reached') {
    return { ...base, kind: 'needs-human', detail: `round cap ${it.maxRounds} reached on #${it.pr}; the agents stop here, over to you` };
  }
  if (!safeBranch(it.headRef) || !safeBranch(it.baseRef)) {
    return { ...base, kind: 'needs-human', detail: `refused branch name ${JSON.stringify(clean(it.headRef))}: only [A-Za-z0-9._/-] is handled` };
  }
  const draftDir = path.join(sdir, 'drafts', it.id.replace(/[^0-9a-z.-]/gi, '_'));
  let clone;
  try {
    clone = prepareClone({ git: deps.git, mainRoot, item: it });
  } catch (e) {
    // kept, not acknowledged: once the human clears the cause the item runs again
    if (e instanceof NeedsHuman) return { ...base, kind: 'needs-human', detail: e.message, keep: true };
    return { ...base, kind: 'needs-human', detail: `could not prepare a clone: ${clean(String(e.stderr || e.message).split('\n')[0])}`, keep: true };
  }
  // the clone exists: a later failure of this item is news again, so the human hears about it
  delete (state.prs[it.pr] ??= {}).blockedItem;
  recordSession(state, it.pr);
  saveState(sdir, state); // a crash during the session still counts the round
  const prompt = buildPrompt({ item: it, me: ctx.me, owners: owners({ ...deps, mainRoot }, ctx, it.files), dryRun: o.dryRun });
  const args = claudeArgs({ kind: it.kind, pr: it.pr, headRef: it.headRef, dryRun: o.dryRun, budgetUsd: o.budgetUsd, model: o.model, cwd: clone.dir });
  const res = runSession({ spawn: deps.spawnClaude, cwd: clone.dir, prompt, args, env: deps.env });
  const copied = collectDrafts({ dir: clone.dir, to: draftDir });
  // questions for the human, each answer as a command to copy (Discord shows them)
  const questions = copied.includes('questions.md') ? parseQuestions(fs.readFileSync(path.join(draftDir, 'questions.md'), 'utf8')) : [];
  // the agent's last message: when it could not write its reply file, the reply is usually in here
  fs.writeFileSync(path.join(draftDir, 'summary.md'), `${res.summary}\n`, { mode: 0o600 });
  fs.writeFileSync(path.join(draftDir, 'session.json'), `${JSON.stringify({ item: it.id, kind: it.kind, ok: res.ok, code: res.code, timedOut: res.timedOut, cost: res.cost, turns: res.turns, subtype: res.subtype, denials: res.denials, summary: res.summary, clone: clone.dir }, null, 2)}\n`, { mode: 0o600 });
  const own = it.kind === 'address-review' || it.kind === 'ci-failed';
  const at = { ...base, path: draftDir, clone: clone.dir, cost: res.cost, ...(questions.length ? { questions, ask: questionsText(it.pr, questions) } : {}) };
  const n = res.denials.length;
  const denied = n ? `; ${n} command${n > 1 ? 's were' : ' was'} denied (see session.json)` : '';
  // every needs-human below keeps the clone and the item: remove the clone to let the watcher retry
  const human = (detail) => ({ ...at, kind: 'needs-human', keep: true, detail: `${detail}${denied}; clone kept at ${clone.dir}, remove it to retry` });
  if (!res.ok) return human(`session failed (${res.timedOut ? 'timed out' : res.subtype || `exit ${res.code}`})`);
  const dirty = own ? deps.git(['-C', clone.dir, 'status', '--porcelain']) : '';
  if (dirty) return human(`uncommitted changes in ${dirty.split('\n').length} file(s) were left; nothing is thrown away`);
  if (!copied.includes('reply.md')) return human(`the session wrote no reply (.iw-watch/reply.md); its last message is in ${path.join(draftDir, 'summary.md')}`);
  if (o.dryRun) {
    const steps = [`cd ${clone.dir}`];
    if (own) steps.push(`git push origin ${it.headRef}`);
    steps.push(`gh pr comment ${it.pr} --body-file ${path.join(draftDir, 'reply.md')}`);
    return { ...at, kind: 'draft-ready', detail: `dry run: nothing was pushed or posted${denied}. To publish: ${steps.join(' && ')}` };
  }
  if (own && pushDenied(res.denials)) return human(`the push was denied; the commits and the reply are kept (drafts ${draftDir})`);
  const left = own ? unpushed({ git: deps.git, dir: clone.dir, headRef: it.headRef }) : 0;
  if (left > 0) return human(`${left} commit${left > 1 ? 's' : ''} not pushed`);
  removeClone({ dir: clone.dir });
  delete at.clone;
  return { ...at, kind: 'done', detail: `${res.summary.slice(0, 500)}${denied}` };
}

function runCmd(deps, ctx, o) {
  if (!deps.claudeAvailable()) {
    deps.stderr('iw-watch: the claude CLI is not on PATH. Install Claude Code (https://code.claude.com/docs) or use the in-session mode: /loop 2m /iw-watch --mine\n');
    return 2;
  }
  const mainRoot = deps.mainRoot || findMainRoot({ git: deps.git });
  const notify = makeNotifier({ env: deps.env, stdout: deps.stdout, stderr: deps.stderr, now: deps.now, spawn: deps.spawnNotify });
  const res = withState(deps, ctx.repo, (state, sdir, lock) => {
    const { items } = scanState(deps, ctx, o, state);
    saveState(sdir, state);
    for (const it of items.slice(0, o.limit)) {
      refreshLock(lock, { now: deps.now });
      const { keep, ...notice } = handle({ deps, ctx, o, state, sdir, mainRoot, it });
      const e = (state.prs[it.pr] ??= {});
      if (keep) {
        // not acknowledged, so it is retried; the human is told once per item, not on every poll
        if (e.blockedItem === it.id) continue;
        e.blockedItem = it.id;
      } else {
        delete e.blockedItem;
        ack(state, it.id);
      }
      saveState(sdir, state);
      notify(notice);
    }
    if (items.length > o.limit) deps.stderr(`iw-watch: ${items.length - o.limit} more item(s) wait for the next run (--limit ${o.limit})\n`);
    return { count: items.length };
  });
  if (!res.skipped && res.count === 0) deps.stderr('iw-watch: nothing new\n');
  return 0;
}

export async function main(argv, deps = defaultDeps()) {
  let o;
  try {
    o = parseArgs(argv);
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    deps.stderr(`iw-watch: ${e.message}\n${USAGE}\n`);
    return 64;
  }
  deps = { ...defaultDeps(), ...deps };
  try {
    if (o.cmd === 'run' && !deps.claudeAvailable()) return runCmd(deps, null, o);
    const ctx = withDomains(deps, context(deps), o);
    if (o.cmd === 'ack') {
      withState(deps, ctx.repo, (state) => { for (const id of o.ids) ack(state, id); });
      deps.stdout(`iw-watch: acknowledged ${o.ids.join(', ')}\n`);
      return 0;
    }
    if (o.cmd === 'scan') {
      const res = withState(deps, ctx.repo, (state) => scanState(deps, ctx, o, state));
      if (!res.skipped) printItems(deps, res.items, o.json);
      return 0;
    }
    return runCmd(deps, ctx, o);
  } catch (e) {
    if (e instanceof GhError) {
      deps.stderr(`iw-watch: ${e.kind}: ${e.message}\n`);
      return 2;
    }
    if (e instanceof DomainError || /not an item id|not pending/.test(e.message)) {
      deps.stderr(`iw-watch: ${e.message}\n`);
      return 64;
    }
    throw e;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; });
}
