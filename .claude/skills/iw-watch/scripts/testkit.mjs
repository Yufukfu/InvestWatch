// Shared test helpers (not a test file): a fake `gh` that answers from saved fixtures, and a CLI harness.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export const fx = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'));
export const REPO = 'Yufukfu/InvestWatch';
export const ME = 'kacpermalczyk';

// A fake `gh` answering from saved fixtures. `over` replaces any route; every call is recorded.
export function fakeGh(over = {}) {
  const pr11 = fx('pr-11.json');
  const pr28 = fx('pr-28.json');
  const routes = {
    'api user': { login: ME },
    'repo view': { nameWithOwner: REPO, defaultBranchRef: { name: 'main' } },
    'pr list mine': [pr11],
    'pr list review': [pr28],
    'pr list reviewed': [],
    'pr list open': [{ number: 11 }, { number: 28 }],
    'pulls/11/reviews': fx('reviews-11.json'),
    'pulls/11/comments': fx('review-comments-11.json'),
    'issues/11/comments': [],
    'pulls/28/reviews': [],
    'pulls/28/comments': [],
    'issues/28/comments': [],
    ...over,
  };
  const calls = [];
  const gh = (args) => {
    calls.push(args);
    const s = args.join(' ');
    let key;
    // the runner's writes: a comment or an issue from a JSON file (--input), answered like GitHub does
    if (args[0] === 'api' && args.includes('POST')) {
      const target = args.find((x) => x.startsWith('repos/'));
      const n = (/issues\/(\d+)\/comments$/.exec(target) || [])[1];
      const v = routes[`POST ${target}`];
      if (v instanceof Error) throw v;
      return v ?? { html_url: n ? `https://github.com/${REPO}/pull/${n}#issuecomment-${calls.length}` : `https://github.com/${REPO}/issues/${900 + calls.length}` };
    }
    if (s.startsWith('issue list')) return structuredClone(routes['issue list'] ?? []);
    if (s.startsWith('pr view') && s.includes('state,headRefOid')) return structuredClone(routes['pr state'] ?? { state: 'OPEN', headRefOid: routes['pr list mine']?.[0]?.headRefOid });
    if (s.startsWith('pr view')) return structuredClone(routes['pr view']);
    if (s === 'api user') key = 'api user';
    else if (s.startsWith('repo view')) key = 'repo view';
    else if (s.startsWith('pr list') && args.includes('--author') && args[args.indexOf('--author') + 1] === '@me') key = 'pr list mine';
    else if (s.startsWith('pr list') && s.includes('review-requested:@me')) key = 'pr list review';
    else if (s.startsWith('pr list') && s.includes('reviewed-by:@me')) key = 'pr list reviewed';
    else if (s.startsWith('pr list') && args.includes('--author')) key = `pr list author ${args[args.indexOf('--author') + 1]}`;
    else if (s.startsWith('pr list') && s.endsWith('--json number')) key = 'pr list open';
    else if (s.startsWith('pr list')) key = 'pr list all';
    else if (/repos\/[^/]+\/[^/]+\/pulls\/\d+$/.test(s)) key = `pr ${/pulls\/(\d+)$/.exec(s)[1]}`;
    else key = (/(pulls|issues)\/\d+\/(reviews|comments|files)/.exec(s) || [])[0];
    const v = key && key.startsWith('pr ') && !(key in routes) ? { author_association: 'COLLABORATOR' } : routes[key];
    if (v instanceof Error) throw v;
    if (v === undefined) throw new Error(`fake gh: no route for ${s}`);
    return structuredClone(v);
  };
  return { gh, calls };
}


export function cli(over = {}, envOver = {}) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-watch-home-'));
  const out = []; const err = [];
  const deps = {
    gh: fakeGh(over).gh,
    env: { XDG_STATE_HOME: path.join(home, 'state'), ...envOver },
    home,
    stdout: (s) => out.push(s),
    stderr: (s) => err.push(s),
    now: () => Date.parse('2026-11-21T22:00:00Z'),
  };
  return { deps, out, err, stateFile: path.join(home, 'state', 'iw-watch', 'Yufukfu__InvestWatch', 'state.json') };
}

