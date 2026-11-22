// Deterministic scan: which GitHub activity is work for me right now. No model, no writes to GitHub.
// It records the event keys of each address-review item as pending in the state (ack moves them to handled);
// the caller saves the state only when the whole scan succeeded.
import { itemId, digest, setPending, isHandled } from './state.mjs';
import { countRounds, capReached, MARKER } from './rounds.mjs';
import { ownedDirs } from './codeowners.mjs';

export class DomainError extends Error {}

const norm = (p) => p.replace(/^\/+|\/+$/g, '');

/**
 * `--domain <dir>` and `--domain mine` -> files => boolean, from CODEOWNERS rules of the default branch.
 * A domain is a CODEOWNERS pattern (`scraper`, `/scraper/` and `scraper/` name the same one); an unknown one
 * is an error, so a typo does not silently watch nothing.
 */
export function domainFilter(rules, domains, me) {
  const wanted = new Set();
  for (const d of domains) {
    if (d === 'mine') {
      const own = ownedDirs(rules, me).map(norm);
      if (!own.length) throw new DomainError(`--domain mine: @${me} owns no directory in CODEOWNERS`);
      own.forEach((p) => wanted.add(p));
    } else if (rules.some((r) => norm(r.pattern) === norm(d))) {
      wanted.add(norm(d));
    } else {
      throw new DomainError(`--domain ${d}: no CODEOWNERS entry for that directory (known: ${rules.map((r) => norm(r.pattern)).join(', ')})`);
    }
  }
  // last match wins, as in GitHub: a file is in the domain only if the rule that owns it is one of the wanted ones
  const owning = (f) => { let hit = null; for (const r of rules) if (r.re.test(f)) hit = r; return hit; };
  return (files) => files.some((f) => { const r = owning(f.replace(/^\.?\//, '')); return Boolean(r && wanted.has(norm(r.pattern))); });
}

const GH_FILES_LIMIT = 100;

/** gh pr list --json files stops at 100 files; a list that long may be cut, so ask the API for all of them */
function filesOf(gh, repo, pr) {
  const files = (pr.files || []).map((f) => f.path);
  if (files.length < GH_FILES_LIMIT) return files;
  return (gh(['api', '--paginate', `repos/${repo}/pulls/${Number(pr.number)}/files?per_page=100`]) || []).map((f) => f.filename);
}

export const PR_FIELDS = 'number,title,url,isDraft,isCrossRepository,mergeable,headRefName,headRefOid,baseRefName,author,updatedAt,statusCheckRollup,files';
export const LIST_LIMIT = 100;
export const OPEN_LIMIT = 500;
// A superseded run is CANCELLED; that is not a failure to fix.
const FAILED = new Set(['FAILURE', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR']);
// Text from people with write access may reach a session that runs tests; anyone else's is dropped.
export const TRUSTED = new Set(['OWNER', 'MEMBER', 'COLLABORATOR']);

const lc = (s) => String(s || '').toLowerCase();
const isBot = (u) => u?.type === 'Bot' || /\[bot\]$/.test(u?.login || '');

function listPrs(gh, extra, warn) {
  const prs = gh(['pr', 'list', '--state', 'open', '--limit', String(LIST_LIMIT), ...extra, '--json', PR_FIELDS]) || [];
  if (prs.length >= LIST_LIMIT) warn(`iw-watch: ${extra.join(' ')} returned ${LIST_LIMIT} PRs, the limit; older ones are not watched`);
  return prs;
}

function activity(gh, repo, n) {
  const get = (p) => gh(['api', '--paginate', `repos/${repo}/${p}?per_page=100`]) || [];
  return { reviews: get(`pulls/${n}/reviews`), reviewComments: get(`pulls/${n}/comments`), comments: get(`issues/${n}/comments`) };
}

function events({ reviews, reviewComments, comments }) {
  const ev = (type, x, at, extra) => ({ key: `${type}:${x.id}`, type, id: x.id, author: x.user?.login, user: x.user, trusted: TRUSTED.has(x.author_association), body: x.body || '', url: x.html_url, at, ...extra });
  return [
    // a review still PENDING is a draft only its author sees
    ...reviews.filter((r) => r.state !== 'PENDING').map((r) => ev('review', r, r.submitted_at, { state: r.state, sha: r.commit_id })),
    ...reviewComments.map((c) => ev('review-comment', c, c.created_at, { path: c.path, line: c.line ?? c.original_line ?? null, inReplyTo: c.in_reply_to_id ?? null, reviewId: c.pull_request_review_id ?? null })),
    ...comments.map((c) => ev('comment', c, c.created_at)),
  ];
}

/** A /iw comment I wrote by hand: mine, starts with /iw, and carries no agent marker */
export const isAnswer = (e, me) => lc(e.author) === lc(me) && /^\/iw\b/.test(e.body.trim()) && !e.body.includes(MARKER) && !/iw-watch agent for @/.test(e.body);

const strip = ({ user, trusted, ...e }) => e;
const byTime = (x, y) => Date.parse(x.at) - Date.parse(y.at) || x.key.localeCompare(y.key);

function base(pr, repo) {
  return {
    repo,
    pr: pr.number,
    title: pr.title,
    url: pr.url,
    author: pr.author?.login,
    headRef: pr.headRefName,
    headSha: pr.headRefOid,
    baseRef: pr.baseRefName,
    isDraft: pr.isDraft,
    crossRepo: Boolean(pr.isCrossRepository),
    files: (pr.files || []).map((f) => f.path),
  };
}

function rounds(act, me, st) {
  return countRounds({ comments: [...act.comments, ...act.reviewComments], me, sessions: st.sessions || 0 });
}

function capItem(b, r, maxRounds, st) {
  if (st.capNotifiedSha === b.headSha) return null;
  return { ...b, id: itemId({ kind: 'cap-reached', pr: b.pr, cursor: b.headSha }), kind: 'cap-reached', rounds: r, maxRounds, events: [], checks: [] };
}

/** Work on my own PRs: review activity by others not handled yet, and failed checks on the head sha */
function minePr(gh, repo, me, pr, st, maxRounds, state) {
  const b = base(pr, repo);
  const act = activity(gh, repo, pr.number);
  // my own comments are not work, except an answer that starts with /iw (questions.mjs). The agents post from
  // my account too, so a comment with the marker is the agent's, never my answer (Adam, PR #48)
  const others = events(act)
    .map((e) => (isAnswer(e, me) ? { ...e, type: 'answer', trusted: true } : e))
    .filter((e) => (lc(e.author) !== lc(me) || e.type === 'answer') && !isBot(e.user) && !isHandled(st, e.key));
  const outsiders = others.filter((e) => !e.trusted).length;
  const fresh = others
    .filter((e) => e.trusted)
    // an approval or a review container with no text is not something to address
    .filter((e) => e.body.trim() !== '' || (e.type === 'review' && e.state === 'CHANGES_REQUESTED'))
    .map(strip)
    .sort(byTime);
  const checks = (pr.statusCheckRollup || [])
    .filter((c) => FAILED.has(c.conclusion) || FAILED.has(c.state))
    .map((c) => ({ name: c.name || c.context, url: c.detailsUrl || c.targetUrl, conclusion: c.conclusion || c.state }));

  const work = [];
  if (fresh.length) work.push({ kind: 'address-review', cursor: digest(fresh.map((e) => e.key)), events: fresh });
  if (checks.length && st.ciFailedSha !== b.headSha) work.push({ kind: 'ci-failed', cursor: b.headSha, events: [], checks });
  // GitHub computes mergeability lazily (UNKNOWN at first); the next poll sees CONFLICTING
  if (pr.mergeable === 'CONFLICTING' && st.conflictSha !== b.headSha) work.push({ kind: 'conflict', cursor: b.headSha, events: [], checks: [] });
  const pending = {};
  let items = [];
  if (work.length) {
    const r = rounds(act, me, st);
    if (capReached(r, maxRounds)) items = [capItem(b, r, maxRounds, st)].filter(Boolean);
    else {
      items = work.map((w) => ({ ...b, id: itemId({ kind: w.kind, pr: b.pr, cursor: w.cursor }), kind: w.kind, rounds: r, maxRounds, events: w.events, checks: w.checks || [], ignoredOutsiders: outsiders }));
      for (const it of items) if (it.kind === 'address-review') pending[it.id] = it.events.map((e) => e.key);
    }
  }
  setPending(state, pr.number, pending);
  return items;
}

/** Someone else's PR that waits for my review at its current head sha */
function reviewPr(gh, repo, me, pr, st, maxRounds, { rereview = false, warn = () => {}, state } = {}) {
  if (pr.isDraft || lc(pr.author?.login) === lc(me)) return [];
  const b = base(pr, repo);
  // a reviewed head needs no new review, unless I answered the agent's question there with /iw
  const answersOnly = st.reviewedSha === b.headSha;
  // a PR is text and code by its author: only someone with write access gets an agent's review session
  const assoc = (gh(['api', `repos/${repo}/pulls/${Number(pr.number)}`]) || {}).author_association;
  if (!TRUSTED.has(assoc)) {
    warn(`iw-watch: #${pr.number} is by @${pr.author?.login} (${assoc || 'unknown'}), outside the team: not handed to an agent`);
    return [];
  }
  const act = activity(gh, repo, pr.number);
  const answers = events(act).filter((e) => isAnswer(e, me) && !isHandled(st, e.key)).map((e) => ({ ...e, type: 'answer', trusted: true }));
  const mine = act.reviews.filter((r) => lc(r.user?.login) === lc(me) && r.state !== 'PENDING');
  if (!answers.length) {
    if (answersOnly || mine.some((r) => r.commit_id === b.headSha)) return [];
    // found only through reviewed-by:@me: re-review a new head unless my last word was an approval
    if (rereview && (!mine.length || mine.at(-1).state === 'APPROVED')) return [];
  }
  const r = rounds(act, me, st);
  if (capReached(r, maxRounds)) return [capItem(b, r, maxRounds, st)].filter(Boolean);
  const keys = new Set(answers.map((e) => e.key));
  const all = [...events(act).filter((e) => !isBot(e.user) && !keys.has(e.key)), ...answers];
  const context = all.filter((e) => e.trusted).map(strip).sort(byTime);
  // `<sha>-<digest>`: ack records the sha as reviewed and the answers as handled (state.mjs)
  const cursor = answers.length ? `${b.headSha}-${digest([...keys])}` : b.headSha;
  const item = { ...b, id: itemId({ kind: 'review', pr: b.pr, cursor }), kind: 'review', rounds: r, maxRounds, events: context, checks: [], ignoredOutsiders: all.length - context.length };
  if (answers.length && state) setPending(state, pr.number, { [item.id]: [...keys] });
  return [item];
}

/**
 * mode: { mine, reviewRequested, author, domainFilter } where domainFilter(files) -> boolean.
 * Returns { items, open }: `open` is the set of open PR numbers, or null when it may be incomplete
 * (then the caller must not drop anything from the state).
 */
export function scan({ gh, repo, me, mode, state, maxRounds = 3, warn = () => {} }) {
  const openList = gh(['pr', 'list', '--state', 'open', '--limit', String(OPEN_LIMIT), '--json', 'number']) || [];
  const open = openList.length >= OPEN_LIMIT ? null : new Set(openList.map((p) => p.number));
  const st = (n) => state.prs[n] || {};
  const keep = (pr) => {
    if (mode.author && lc(pr.author?.login) !== lc(mode.author)) return false;
    if (!mode.domainFilter) return true;
    const files = filesOf(gh, repo, pr);
    pr.files = files.map((p) => ({ path: p }));
    return mode.domainFilter(files);
  };
  const items = [];
  const done = new Set();
  if (mode.mine) {
    for (const pr of listPrs(gh, ['--author', '@me'], warn).filter(keep)) {
      done.add(pr.number);
      items.push(...minePr(gh, repo, me, pr, st(pr.number), maxRounds, state));
    }
  }
  const sources = [];
  if (mode.reviewRequested) {
    sources.push({ prs: listPrs(gh, ['--search', 'review-requested:@me'], warn) });
    // GitHub clears the request once I submit a review, so a new head after it is found this way
    sources.push({ prs: listPrs(gh, ['--search', 'reviewed-by:@me'], warn), rereview: true });
  }
  // --author or --domain alone: watch every matching PR by someone else as a review
  if (!mode.mine && !mode.reviewRequested && (mode.author || mode.domainFilter)) {
    sources.push({ prs: listPrs(gh, mode.author ? ['--author', mode.author] : [], warn) });
  }
  for (const { prs, rereview } of sources) {
    for (const pr of prs.filter(keep)) {
      if (done.has(pr.number)) continue;
      done.add(pr.number);
      items.push(...reviewPr(gh, repo, me, pr, st(pr.number), maxRounds, { rereview, warn, state }));
    }
  }
  items.sort((x, y) => x.pr - y.pr || x.kind.localeCompare(y.kind));
  return { items, open };
}
