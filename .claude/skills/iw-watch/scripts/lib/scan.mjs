// Deterministic scan: which GitHub activity is work for me right now. No model, no writes to GitHub.
// Returns work items; the state is only read here (ack moves it), except closed PRs, which the caller drops.
import { itemId } from './state.mjs';
import { countRounds, capReached } from './rounds.mjs';

export const PR_FIELDS = 'number,title,url,isDraft,headRefName,headRefOid,baseRefName,author,updatedAt,statusCheckRollup,files';
const LIMIT = '50';
const FAILED = new Set(['FAILURE', 'TIMED_OUT', 'CANCELLED', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR']);

const lc = (s) => String(s || '').toLowerCase();
const isBot = (u) => u?.type === 'Bot' || /\[bot\]$/.test(u?.login || '');

function listPrs(gh, extra) {
  return gh(['pr', 'list', '--state', 'open', '--limit', LIMIT, ...extra, '--json', PR_FIELDS]) || [];
}

function activity(gh, repo, n) {
  const get = (p) => gh(['api', `repos/${repo}/${p}?per_page=100`]) || [];
  return { reviews: get(`pulls/${n}/reviews`), reviewComments: get(`pulls/${n}/comments`), comments: get(`issues/${n}/comments`) };
}

function events({ reviews, reviewComments, comments }) {
  return [
    ...reviews.map((r) => ({ type: 'review', id: r.id, author: r.user?.login, user: r.user, state: r.state, body: r.body || '', url: r.html_url, at: r.submitted_at, sha: r.commit_id })),
    ...reviewComments.map((c) => ({ type: 'review-comment', id: c.id, author: c.user?.login, user: c.user, body: c.body || '', url: c.html_url, at: c.created_at, path: c.path, line: c.line ?? c.original_line ?? null, inReplyTo: c.in_reply_to_id ?? null })),
    ...comments.map((c) => ({ type: 'comment', id: c.id, author: c.user?.login, user: c.user, body: c.body || '', url: c.html_url, at: c.created_at })),
  ];
}

const strip = ({ user, ...e }) => e;

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
    files: (pr.files || []).map((f) => f.path),
  };
}

function rounds(act, me, st) {
  return countRounds({ comments: [...act.comments, ...act.reviewComments], me, sessions: st.sessions || 0 });
}

function capItem(b, r, maxRounds, st) {
  if (st.capNotifiedSha === b.headSha) return null;
  return { ...b, id: itemId({ kind: 'cap-reached', pr: b.pr, cursor: b.headSha }), kind: 'cap-reached', rounds: r, maxRounds, events: [] };
}

/** Work on my own PRs: new review activity by others, and failed checks on the head sha */
function minePr(gh, repo, me, pr, st, maxRounds) {
  const b = base(pr, repo);
  const act = activity(gh, repo, pr.number);
  const seen = st.seenAt ? Date.parse(st.seenAt) : -Infinity;
  const fresh = events(act)
    .filter((e) => lc(e.author) !== lc(me) && !isBot(e.user))
    .filter((e) => Date.parse(e.at) > seen)
    // an approval or a bare review container with no text is not something to address
    .filter((e) => e.body.trim() !== '' || (e.type === 'review' && e.state === 'CHANGES_REQUESTED'))
    .map(strip)
    .sort((x, y) => Date.parse(x.at) - Date.parse(y.at));
  const checks = (pr.statusCheckRollup || [])
    .filter((c) => FAILED.has(c.conclusion) || FAILED.has(c.state))
    .map((c) => ({ name: c.name || c.context, url: c.detailsUrl || c.targetUrl, conclusion: c.conclusion || c.state }));

  const work = [];
  if (fresh.length) work.push({ kind: 'address-review', cursor: fresh.at(-1).at, events: fresh });
  if (checks.length && st.ciFailedSha !== b.headSha) work.push({ kind: 'ci-failed', cursor: b.headSha, events: [], checks });
  if (!work.length) return [];
  const r = rounds(act, me, st);
  if (capReached(r, maxRounds)) return [capItem(b, r, maxRounds, st)].filter(Boolean);
  return work.map((w) => ({ ...b, id: itemId({ kind: w.kind, pr: b.pr, cursor: w.cursor }), kind: w.kind, rounds: r, maxRounds, events: w.events, checks: w.checks || [] }));
}

/** Someone else's PR that waits for my review at its current head sha */
function reviewPr(gh, repo, me, pr, st, maxRounds) {
  if (pr.isDraft || lc(pr.author?.login) === lc(me)) return [];
  const b = base(pr, repo);
  if (st.reviewedSha === b.headSha) return [];
  const act = activity(gh, repo, pr.number);
  if (act.reviews.some((r) => lc(r.user?.login) === lc(me) && r.commit_id === b.headSha)) return [];
  const r = rounds(act, me, st);
  if (capReached(r, maxRounds)) return [capItem(b, r, maxRounds, st)].filter(Boolean);
  const context = events(act).filter((e) => !isBot(e.user)).map(strip).sort((x, y) => Date.parse(x.at) - Date.parse(y.at));
  return [{ ...b, id: itemId({ kind: 'review', pr: b.pr, cursor: b.headSha }), kind: 'review', rounds: r, maxRounds, events: context, checks: [] }];
}

/**
 * mode: { mine, reviewRequested, author, domainFilter } where domainFilter(files) -> boolean (group 5).
 * Returns { items, open } with `open` the numbers of every open PR, for dropping closed ones from the state.
 */
export function scan({ gh, repo, me, mode, state, maxRounds = 3 }) {
  const open = new Set((gh(['pr', 'list', '--state', 'open', '--limit', '200', '--json', 'number']) || []).map((p) => p.number));
  const st = (n) => state.prs[n] || {};
  const keep = (pr) => (!mode.author || lc(pr.author?.login) === lc(mode.author)) && (!mode.domainFilter || mode.domainFilter((pr.files || []).map((f) => f.path)));
  const items = [];
  const done = new Set();
  if (mode.mine) {
    for (const pr of listPrs(gh, ['--author', '@me']).filter(keep)) {
      done.add(pr.number);
      items.push(...minePr(gh, repo, me, pr, st(pr.number), maxRounds));
    }
  }
  const reviewSources = [];
  if (mode.reviewRequested) reviewSources.push(listPrs(gh, ['--search', 'review-requested:@me']));
  // --author or --domain alone: watch every matching PR by someone else as a review
  if (!mode.mine && !mode.reviewRequested && (mode.author || mode.domainFilter)) {
    reviewSources.push(listPrs(gh, mode.author ? ['--author', mode.author] : []));
  }
  for (const pr of reviewSources.flat().filter(keep)) {
    if (done.has(pr.number)) continue;
    done.add(pr.number);
    items.push(...reviewPr(gh, repo, me, pr, st(pr.number), maxRounds));
  }
  items.sort((x, y) => x.pr - y.pr || x.kind.localeCompare(y.kind));
  return { items, open };
}
