#!/usr/bin/env node
// iw-watch runner. The runner decides what to do (poll, filter, dedupe, cap); the model decides how.
//   watch.mjs scan [--mine] [--review-requested] [--author L] [--max-rounds N] [--json]
//   watch.mjs ack <item-id>...
//   watch.mjs notify <done|needs-human|approved> --pr N [--link <comment url>] [--questions <file>] [--note <text>]
//     (in-session mode: the agent sends its Discord notice; the questions file becomes /iw comments to paste)
//   watch.mjs run  [same filters] [--publish] [--limit N] [--budget-usd X] [--model M]   (a dry run unless --publish)
// Exit codes: 0 ok (also "already running"), 2 GitHub or environment error, 64 usage error.
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawnSync, execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { makeGh, GhError } from './lib/gh.mjs';
import { scan, domainFilter, DomainError } from './lib/scan.mjs';
import { stateDir, loadState, saveState, ack, dropClosed, acquireLock, releaseLock, refreshLock, recordSession } from './lib/state.mjs';
import { loadCodeowners, ownerOf } from './lib/codeowners.mjs';
import { buildPrompt, safeBranch } from './lib/prompt.mjs';
import { claudeArgs, runSession, childEnv, denyReadPaths } from './lib/session.mjs';
import { prepareClone, unpushed, removeClone, collectDrafts, findMainRoot, realGit, NeedsHuman, newCommitPaths, pushBranch, installDeps, findEnvFiles, gitSnapshot, startMerge, finishMerge, pushedContent } from './lib/worktree.mjs';
import { makeNotifier, KINDS } from './lib/notify.mjs';
import { parseQuestions, questionsText } from './lib/questions.mjs';
import { MARKER } from './lib/rounds.mjs';

const USAGE = `usage: watch.mjs scan|run [--mine] [--review-requested] [--author <login>] [--domain <dir>|mine]
                 [--max-rounds N] [--json]                                  (scan)
                 [--publish] [--limit N] [--budget-usd X] [--model M]       (run; dry unless --publish)
       watch.mjs ack <item-id>...
       watch.mjs notify <done|needs-human|approved> --pr N [--link <url>] [--questions <file>] [--note <text>]`;

class UsageError extends Error {}

export function parseArgs(argv) {
  const [cmd, ...rest] = argv;
  if (!['scan', 'ack', 'run', 'notify'].includes(cmd)) throw new UsageError(`unknown command ${JSON.stringify(cmd ?? '')}`);
  if (cmd === 'notify') return parseNotify(rest);
  const o = { cmd, mine: false, reviewRequested: false, author: null, domains: [], maxRounds: 3, json: false, dryRun: true, publish: false, limit: null, budgetUsd: 2, model: null, ids: [] };
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
    else if (a === '--dry-run') o.forceDry = true;
    else if (a === '--publish') o.publish = true;
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
  if (cmd === 'scan' && (o.forceDry || o.publish || o.limit !== null || o.model)) throw new UsageError('--dry-run, --publish, --limit and --model apply to run only');
  if (o.forceDry && o.publish) throw new UsageError('--dry-run and --publish exclude each other');
  // unattended runs draft by default (Adam, PR #48): pushing and posting needs --publish
  o.dryRun = !o.publish;
  delete o.forceDry;
  if (cmd !== 'ack' && !o.mine && !o.reviewRequested && !o.author && !o.domains.length) {
    throw new UsageError('say what to watch: --mine, --review-requested, --author <login> or --domain <dir>');
  }
  o.limit ??= 3;
  return o;
}

function parseNotify(rest) {
  const o = { cmd: 'notify', kind: rest.shift(), pr: null, link: null, questions: null, note: '' };
  if (!KINDS.includes(o.kind)) throw new UsageError(`notify needs a kind first: ${KINDS.join(', ')}`);
  while (rest.length) {
    const a = rest.shift();
    const v = rest.shift();
    if (v === undefined) throw new UsageError(`${a} needs a value`);
    if (a === '--pr') o.pr = Number(v);
    else if (a === '--link') o.link = v;
    else if (a === '--questions') o.questions = v;
    else if (a === '--note') o.note = v;
    else throw new UsageError(`unknown argument ${JSON.stringify(a)}`);
  }
  if (!Number.isInteger(o.pr) || o.pr < 1) throw new UsageError('notify needs --pr <number>');
  return o;
}

/** In-session notice: title and URL come from GitHub, the link must be this PR's, the questions from a file */
function notifyCmd(deps, ctx, o) {
  const pr = deps.gh(['pr', 'view', String(o.pr), '--json', 'number,title,url']);
  const link = o.link && new RegExp(`^https://github\\.com/${ctx.repo.replace('/', '\\/')}/(pull|issues)/${o.pr}(#issuecomment-\\d+)?$`).test(o.link) ? o.link : null;
  if (o.link && !link) deps.stderr(`iw-watch: --link is not a link into #${o.pr}; the PR link is used\n`);
  const questions = o.questions ? parseQuestions(fs.readFileSync(o.questions, 'utf8')) : [];
  const note = clean(o.note).slice(0, 300);
  makeNotifier({ env: deps.env, stdout: deps.stdout, stderr: deps.stderr, now: deps.now, spawn: deps.spawnNotify })({
    pr: pr.number, title: pr.title, url: pr.url, ...(link ? { link } : {}), kind: questions.length && o.kind === 'done' ? 'needs-human' : o.kind,
    ...(note ? { detail: note } : {}), ...(questions.length ? { questions, ask: questionsText(questions) } : {}),
  });
  return 0;
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
    exec: execFileSync,
    claudeAvailable: () => !spawnSync('claude', ['--version'], { stdio: 'ignore' }).error,
    gitIdentityProblem: () => gitIdentityProblem(process.env),
  };
}

/**
 * Why git could not commit in the runner's clones, or null (#127). The runner commits conflict merges itself and the
 * agent commits its fixes, in fresh clones that never get the main checkout's local `user.*`, so ask git outside any
 * repository, as a new clone would: global and system config plus the GIT_* environment. A Linux runner or a cron or
 * launchd job without a global identity fails here instead of after an agent session.
 */
export function gitIdentityProblem(env) {
  for (const v of ['GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT']) {
    const r = spawnSync('git', ['var', v], { cwd: os.tmpdir(), env, encoding: 'utf8' });
    if (r.error) return `git is not runnable: ${r.error.message}`;
    if (r.status !== 0) return (String(r.stderr).trim().split('\n').find((l) => /identity unknown|fatal/i.test(l)) || `git var ${v} failed`).trim();
  }
  return null;
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
    const who = it.kind === 'review' ? `by ${it.author}` : it.kind === 'approved' ? `by ${(it.approvers || []).join(',') || '?'}` : `${it.events.length} new`;
    deps.stdout(`#${it.pr} ${it.kind.padEnd(14)} ${clean(who).padEnd(16)} ${it.kind === 'approved' ? 'can merge  ' : `round ${it.rounds}/${it.maxRounds}`}  ${clean(it.title)}\n    ${clean(it.url)}\n    id: ${it.id}\n`);
  }
}

// Titles and logins are other people's text: no terminal escape sequences reach the terminal
export const clean = (s) => String(s ?? '').replace(/[\u0000-\u001f\u007f-\u009f]/g, '?');

function scanState(deps, ctx, o, state) {
  const mode = { mine: o.mine, reviewRequested: o.reviewRequested, author: o.author, domainFilter: ctx.domainFilter };
  const r = scan({ gh: deps.gh, repo: ctx.repo, me: ctx.me, mode, state, maxRounds: o.maxRounds, defaultBranch: ctx.defaultBranch, warn: (m) => deps.stderr(`${m}\n`) });
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
  // nothing for an agent to do: tell the human they can merge
  if (it.kind === 'approved') return { ...base, kind: 'approved', ...(it.approvers?.length ? { detail: `approved by ${it.approvers.map((a) => `@${clean(a)}`).join(', ')}` } : {}) };
  if (it.kind === 'cap-reached') {
    return { ...base, kind: 'needs-human', detail: `round cap ${it.maxRounds} reached on #${it.pr}; the agents stop here, over to you` };
  }
  if (!safeBranch(it.headRef) || !safeBranch(it.baseRef)) {
    return { ...base, kind: 'needs-human', detail: `refused branch name ${JSON.stringify(clean(it.headRef))}: only [A-Za-z0-9._/-] is handled` };
  }
  const own = ['address-review', 'ci-failed', 'conflict'].includes(it.kind);
  // the push target: this repository's PR branch, never a fork's, never the base or default branch
  if (own && it.crossRepo) return { ...base, kind: 'needs-human', detail: `#${it.pr} comes from a fork; an agent does not push to it` };
  if (own && [it.baseRef, ctx.defaultBranch, 'main', 'master'].includes(it.headRef)) {
    return { ...base, kind: 'needs-human', detail: `#${it.pr} has ${it.headRef} as its head branch; an agent never pushes to it` };
  }
  // the clone checks out the base branch (a review) or diffs against it (a fix): only the default branch is trusted
  if (it.baseRef !== ctx.defaultBranch) {
    return { ...base, kind: 'needs-human', detail: `#${it.pr} targets ${it.baseRef}, not ${ctx.defaultBranch}; an agent runs only on PRs into the default branch` };
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
  // a dry run is not a round: turning --publish on later must still get to handle the PR
  if (!o.dryRun) recordSession(state, it.pr);
  saveState(sdir, state); // a crash during the session still counts the round
  // the session has no network: the runner installs the lockfiles, without install scripts
  if (own) installDeps({ run: deps.exec, dir: clone.dir, files: it.files, env: childEnv(deps.env) });
  const before = gitSnapshot({ dir: clone.dir });
  const fileOwners = owners({ ...deps, mainRoot }, ctx, it.files);
  const safe = (args, opts) => deps.git(['-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', ...args], opts);
  let res;
  if (it.kind === 'conflict') {
    // the runner merges the base; the agent only resolves what git could not, and the runner commits the merge
    const merged = startMerge({ git: safe, dir: clone.dir, baseRef: it.baseRef });
    if (merged.refused) return { ...base, kind: 'needs-human', clone: clone.dir, keep: true, detail: `${merged.refused}; clone kept at ${clone.dir}, remove it to retry` };
    it.conflictFiles = merged.files;
    if (!merged.files.length) {
      fs.mkdirSync(path.join(clone.dir, '.iw-watch'), { recursive: true });
      fs.writeFileSync(path.join(clone.dir, '.iw-watch', 'reply.md'), `Merged \`origin/${it.baseRef}\` into \`${it.headRef}\`: git resolved it without conflicts here. No other change.\n`);
      res = { ok: true, denials: [], cost: 0, summary: `merged origin/${it.baseRef} without conflicts` };
    }
  }
  if (!res) {
    const prompt = buildPrompt({ item: it, me: ctx.me, owners: fileOwners, dryRun: o.dryRun });
    const denyRead = denyReadPaths({ home: deps.home, stateDir: sdir, configDir: deps.env.CLAUDE_CONFIG_DIR, envFiles: findEnvFiles({ mainRoot }) });
    const args = claudeArgs({ kind: it.kind, pr: it.pr, baseRef: it.baseRef, budgetUsd: o.budgetUsd, model: o.model, denyRead, cwd: clone.dir });
    res = runSession({ spawn: deps.spawnClaude, cwd: clone.dir, prompt, args, env: deps.env });
  }
  const copied = collectDrafts({ dir: clone.dir, to: draftDir });
  // questions for the human, each answer as a command to copy (Discord shows them)
  const questions = copied.includes('questions.md') ? parseQuestions(fs.readFileSync(path.join(draftDir, 'questions.md'), 'utf8')) : [];
  // the agent's last message: when it could not write its reply file, the reply is usually in here
  fs.writeFileSync(path.join(draftDir, 'summary.md'), `${res.summary}\n`, { mode: 0o600 });
  fs.writeFileSync(path.join(draftDir, 'session.json'), `${JSON.stringify({ item: it.id, kind: it.kind, ok: res.ok, code: res.code, timedOut: res.timedOut, cost: res.cost, turns: res.turns, subtype: res.subtype, denials: res.denials, summary: res.summary, clone: clone.dir }, null, 2)}\n`, { mode: 0o600 });
  const at = { ...base, path: draftDir, clone: clone.dir, cost: res.cost, ...(questions.length ? { questions, ask: questionsText(questions) } : {}) };
  const n = res.denials.length;
  const denied = n ? `; ${n} command${n > 1 ? 's were' : ' was'} denied (see session.json)` : '';
  // every needs-human below keeps the clone and the item: remove the clone to let the watcher retry
  const human = (detail) => ({ ...at, kind: 'needs-human', keep: true, detail: `${detail}${denied}; clone kept at ${clone.dir}, remove it to retry` });
  if (!res.ok) return human(`session failed (${res.timedOut ? 'timed out' : res.subtype || `exit ${res.code}`})`);
  // sandboxed code can write .git/: a changed config or hook would run, outside the sandbox, in the git calls below
  if (gitSnapshot({ dir: clone.dir }) !== before) return human('the session changed .git/config, .git/hooks or .git/info/attributes; the runner runs no git in this clone');
  const git = safe;
  if (it.kind === 'conflict') {
    const left = finishMerge({ git, dir: clone.dir, files: it.conflictFiles, headRef: it.headRef, baseRef: it.baseRef, baseSha: clone.baseSha });
    if (left) return human(left);
  }
  const dirty = own ? git(['-C', clone.dir, 'status', '--porcelain']) : '';
  if (dirty) return human(`uncommitted changes in ${dirty.split('\n').length} file(s) were left; nothing is thrown away`);
  if (!copied.includes('reply.md')) return human(`the session wrote no reply (.iw-watch/reply.md); its last message is in ${path.join(draftDir, 'summary.md')}`);
  // the agent's commits are checked before anything leaves the machine
  const bad = own ? newCommitPaths({ git, dir: clone.dir, headSha: clone.head, baseSha: clone.baseSha }) : [];
  if (bad.length) return human(`the agent's commits change ${bad.slice(0, 3).join(', ')}; the runner does not push settings, hooks, CI or agent instructions`);
  const body = postBody({ me: ctx.me, it, text: fs.readFileSync(path.join(draftDir, 'reply.md'), 'utf8') });
  const issueText = copied.includes('issue.md') ? fs.readFileSync(path.join(draftDir, 'issue.md'), 'utf8') : '';
  // a test the agent ran can write into its own reply: never post what looks like a credential
  if (leaks(`${body}\n${issueText}`, deps.env)) return human('the reply or the issue contains something that looks like a credential; nothing is posted, check the drafts');
  // the commits are scanned too: a test can write a secret into a fixture or a commit message
  if (own) {
    const pushed = pushedContent({ git, dir: clone.dir, headSha: clone.head, baseSha: clone.baseSha });
    if (pushed.binary.length) return human(`the agent's commits add binary files (${pushed.binary.slice(0, 3).join(', ')}); the runner pushes text only`);
    if (pushed.text.length > 2 * 1024 * 1024) return human('the agent\'s commits are larger than 2 MB; the runner does not push them');
    if (leaks(pushed.text, deps.env)) return human('the agent\'s commits contain something that looks like a credential; nothing is pushed');
  }
  fs.writeFileSync(path.join(draftDir, 'post.json'), JSON.stringify({ body }), { mode: 0o600 });
  if (o.dryRun) {
    return { ...at, kind: 'draft-ready', detail: `dry run: nothing was pushed or posted${denied}. The draft reply is in ${path.join(draftDir, 'reply.md')}; run with --publish to push and post` };
  }
  const left = own ? unpushed({ git, dir: clone.dir, headRef: it.headRef }) : 0;
  // the PR must still be open and at the head the agent worked on: a merged PR with a deleted branch would be recreated
  let now;
  try { now = deps.gh(['pr', 'view', String(it.pr), '--json', 'state,headRefOid']); } catch (e) { return human(`could not re-check #${it.pr} before publishing: ${clean(e.message)}`); }
  if (now?.state !== 'OPEN') return human(`#${it.pr} is ${String(now?.state || 'gone').toLowerCase()} now; nothing is pushed or posted`);
  if (own && now.headRefOid !== clone.head) return human(`#${it.pr} moved to ${String(now.headRefOid).slice(0, 12)} while the agent worked; nothing is pushed`);
  if (left > 0) {
    try {
      pushBranch({ git, dir: clone.dir, headRef: it.headRef });
    } catch (e) {
      return human(`the push of ${left} commit${left > 1 ? 's' : ''} failed (${clean(String(e.stderr || e.message).split('\n')[0])}); a teammate may have pushed meanwhile`);
    }
  }
  let link;
  try {
    link = deps.gh(['api', '-X', 'POST', `repos/${ctx.repo}/issues/${Number(it.pr)}/comments`, '--input', path.join(draftDir, 'post.json')])?.html_url;
  } catch (e) {
    return human(`${left ? 'pushed, but ' : ''}posting the reply failed: ${clean(e.message)}`);
  }
  if (link) at.link = link;
  const issue = copied.includes('issue.md') ? openIssue({ deps, ctx, it, draftDir, owners: fileOwners }) : null;
  removeClone({ dir: clone.dir });
  delete at.clone;
  return { ...at, kind: 'done', ...(issue ? { issue } : {}), detail: `${res.summary.slice(0, 500)}${denied}${issue?.url ? `; issue ${issue.url}` : issue?.skipped ? `; issue not opened: ${issue.skipped}` : ''}` };
}

const REPLY_LIMIT = 60000;
const TOKEN = /sk-ant-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|discord(?:app)?\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+/;

/** A known token shape, or the literal value of any secret-looking variable the runner holds */
export function leaks(text, env = {}) {
  if (TOKEN.test(text)) return true;
  return Object.entries(env).some(([k, v]) => /TOKEN|KEY|SECRET|PASS|WEBHOOK|AUTH|CREDENTIAL/i.test(k) && typeof v === 'string' && v.length >= 12 && text.includes(v));
}

/** What the runner posts: a visible agent line first (all agents post from human accounts), the marker last */
export function postBody({ me, it, text }) {
  const reply = String(text).split(MARKER).join('').trim().slice(0, REPLY_LIMIT);
  return `> iw-watch agent for @${me}, round ${it.rounds + 1}/${it.maxRounds}\n\n${reply}\n\n${MARKER}\n`;
}

/** .iw-watch/issue.md: `# title`, `assignee: login|none`, body. The owner must be in CODEOWNERS; no duplicate titles. */
function openIssue({ deps, ctx, it, draftDir, owners: fileOwners }) {
  const [first = '', second = '', ...rest] = fs.readFileSync(path.join(draftDir, 'issue.md'), 'utf8').split('\n');
  const title = first.replace(/^#\s*/, '').replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 200);
  if (!title) return { skipped: 'issue.md has no title line' };
  const asked = (/^assignee:\s*@?([A-Za-z0-9-]+)\s*$/i.exec(second) || [])[1];
  const known = new Set(fileOwners.flatMap((f) => f.owners).filter((o) => !o.includes('/')).map((o) => o.toLowerCase()));
  const assignee = asked && asked.toLowerCase() !== 'none' && known.has(asked.toLowerCase()) ? asked : null;
  const norm = (s) => s.toLowerCase().replace(/\s+/g, '');
  try {
    const open = deps.gh(['issue', 'list', '--state', 'open', '--limit', '100', '--search', `${title} in:title`, '--json', 'number,title,url']) || [];
    const dup = open.find((x) => norm(x.title) === norm(title));
    if (dup) return { skipped: `a duplicate is open: ${dup.url}` };
    const body = postBody({ me: ctx.me, it, text: `${rest.join('\n').trim()}\n\nFound while handling ${it.url}.${asked && !assignee ? ` Proposed owner @${asked} is not in CODEOWNERS for the changed files, so nobody is assigned.` : ''}` });
    const file = path.join(draftDir, 'issue.json');
    fs.writeFileSync(file, JSON.stringify({ title, body, ...(assignee ? { assignees: [assignee] } : {}) }), { mode: 0o600 });
    const made = deps.gh(['api', '-X', 'POST', `repos/${ctx.repo}/issues`, '--input', file]);
    return { url: made?.html_url, assignee };
  } catch (e) {
    return { skipped: clean(e.message) };
  }
}

function runCmd(deps, ctx, o) {
  if (!deps.claudeAvailable()) {
    deps.stderr('iw-watch: the claude CLI is not on PATH. Install Claude Code (https://code.claude.com/docs) or use the in-session mode: /loop 2m /iw-watch --mine\n');
    return 2;
  }
  const noIdentity = deps.gitIdentityProblem();
  if (noIdentity) {
    deps.stderr(`iw-watch: no git identity to commit with (${noIdentity}). The runner and the agent commit in fresh clones, which only see your global git config: run git config --global user.name "Your Name" and git config --global user.email "you@example.com", or set GIT_AUTHOR_NAME/EMAIL and GIT_COMMITTER_NAME/EMAIL in the cron or launchd job\n`);
    return 2;
  }
  const mainRoot = deps.mainRoot || findMainRoot({ git: deps.git });
  const notify = makeNotifier({ env: deps.env, stdout: deps.stdout, stderr: deps.stderr, now: deps.now, spawn: deps.spawnNotify });
  const res = withState(deps, ctx.repo, (state, sdir, lock) => {
    const { items } = scanState(deps, ctx, o, state);
    saveState(sdir, state);
    // --limit bounds the sessions; an approved notice starts none, so it never takes a slot from real work
    const work = items.filter((it) => it.kind !== 'approved');
    const told = items.filter((it) => it.kind === 'approved');
    for (const it of [...work.slice(0, o.limit), ...told]) {
      refreshLock(lock, { now: deps.now });
      let r;
      try {
        r = handle({ deps, ctx, o, state, sdir, mainRoot, it });
      } catch (e) {
        // one broken item does not stop the run; it is kept, so it is retried once the cause is gone
        r = { pr: it.pr, title: it.title, url: it.url, item: it.id, kindOfItem: it.kind, kind: 'needs-human', keep: true, detail: `the runner failed on this item: ${clean(String(e.stderr || e.message).split('\n')[0])}` };
      }
      const { keep, ...notice } = r;
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
    if (work.length > o.limit) deps.stderr(`iw-watch: ${work.length - o.limit} more item(s) wait for the next run (--limit ${o.limit})\n`);
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
    if (o.cmd === 'run' && (!deps.claudeAvailable() || deps.gitIdentityProblem())) return runCmd(deps, null, o);
    if (o.cmd === 'notify') return notifyCmd(deps, context(deps), o);
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
